#!/usr/bin/env python
# coding: utf-8

# To do:
# How many increments can my XLP do?  
# Need to do some calibration?  Is it less than the real value due to dead volume and backlash etc. ?
# Ask Louis again about the order of the ports on the valve?
# Reason for using re library ?

import time
import re
import serial 
import numpy as np
import math



class XLPdriver:
    
    def __init__(self, serial_port):  # Init function starts serial communication
        self.hang_counter = 0
        self.serialCom = serial.Serial(  # Initialize serial communication object
            port=serial_port,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        # set speed to 200 - the default of 900 is too fast with a 25 mL syringe
        self.serialCom.write(bytearray("/1V200R\r\n", "ascii"))

        # not sure what Louis' active port was doing?
        self.resolution = 6000 # XLP6000 has a resolution of 6000 increments in normal (non-microstepping) mode
        self.syringe_size = 25 #syringe size in mL

        # volumes of tubing for each of the 12 lines in mL (cut all tubes to same length, calculate volume suing ID etc, then test and adjust as necessary)
        self.input1TubeVol = 3.06 # tube at port 1
        self.input2TubeVol = 3.06 # tube at port 2
        self.input3TubeVol = 3.06 # tube at port 3
        self.input4TubeVol = 3.06 # tube at port 4
        self.input5TubeVol = 3.06 # tube at port 5
        self.washTubeVol = 3.06 # tube at port 6
        self.wasteTubeVol = 1.05 # tube at port 7
        self.output1TubeVol = 1.05 # tube at port 8
        self.output2TubeVol = 1.05 # tube at port 9
        self.output3TubeVol = 1.05 # tube at port 10
        self.output4TubeVol = 1.05 # tube at port 11
        self.output5TubeVol = 1.05 # tube at port 12

        self.input1Port = 1
        self.input2Port = 2
        self.input3Port = 3
        self.input4Port = 4
        self.input5Port = 5
        self.washPort = 6
        self.wastePort = 7
        self.output1Port = 8
        self.output2Port = 9
        self.output3Port = 10
        self.output4Port = 11
        self.output5Port = 12

        self.reagent1Primed = False
        self.reagent2Primed = False
        self.reagent3Primed = False
        self.reagent4Primed = False
        self.reagent5Primed = False
        
    def __str__(self): 
      
        self.serialCom.write(bytearray("/1?76\r\n", "ascii"))
        x = self.serialCom.read_until("\n")
        pump_config = str(x)[9:-9] 
        
        self.serialCom.write(bytearray("/1?6\r\n", "ascii"))
        x = self.serialCom.read_until("\n")
        pump_valve = str(x)[9:-9]
        
        self.serialCom.write(bytearray("/1?\r\n", "ascii"))
        x = self.serialCom.read_until("\n")
        pump_pos = str(x)[9:-9]
        
        self.serialCom.write(bytearray("/1?15\r\n", "ascii"))
        x = self.serialCom.read_until("\n")
        no_init = str(x)[9:-9]

        self.serialCom.write(bytearray("/1?16\r\n", "ascii"))
        x = self.serialCom.read_until("\n")
        no_plunger_moves = str(x)[9:-9]

        self.serialCom.write(bytearray("/1?17\r\n", "ascii"))
        x = self.serialCom.read_until("\n")
        no_valve_moves = str(x)[9:-9]
        
        # ADD REPORTING HERE FOR SPEED
        out_string =    f"""
                        Pump Model: Tecan Cavro XLP 6000 Modular Syringe Pump
                        Pump Address: 1
                        Syringe Volume: 25 ml
                        Pump current configuration: {pump_config}
                        Number of pump initialisations: {no_init}
                        Number of plunger movements: {no_plunger_moves}
                        Number of valve movements: {no_valve_moves}
                        
                        Current set-valve: {pump_valve}
                        Current plunger position: Increment {pump_pos}
                        
                        """
        return out_string
        
    #close serial connection if need be.
    def close(self):
        self.serialCom.close()
    
    #call to terminate running command - can be used to perform an emergency stop.
    #if used the pump must be re-initialised to prevent lost increments.
    def terminate(self):
        self.serialCom.write(bytearray("/1T\r\n", "ascii"))
        print('Running command terminated prematurely.  Initialise pump before using again.')
        
    #reads pump response - must read /0` before proceeding with commands.
    def readResponse(self):
        self.serialCom.write(bytearray("/1Q\r\n", "ascii"))
        x = self.serialCom.read_until("\n")
        stringx = str(x)
        print(f'stringx is: {stringx}')
        response = re.search('/0+[@`a-zA-Z]', stringx)
        print(response)
        
        #can only repeat call 10 times before leaving loop and demanding user input.
        if self.hang_counter >= 10: # tell Louis about needing to clear this else it will reach a point it is always over 10
            raise Exception('Error/busy status not clearing') 
            
        if response:
            code = response.string
            print(f'code is: {code}') # code seems to be the same as stringx ??? what's the point of the extra steps 

            search = re.search('/0`', code) #error free and non-busy -> the only proceed condition
            if search:
                print('No error')
                self.hang_counter = 0
                return '/0`'
        
            search = re.search('/0+[@]', code) #immediate errors waits, calls again to resolve
            if search:
                time.sleep(0.1) 
                print('Pump busy')
                self.hang_counter += 1
                self.readResponse()
            
            search = re.search('/0+[bBCcDdKk]', code) #invalid input error    #don't understand all these letters... bBcCdD ??? -> check these error codes with Louis!!!
            if search:
                self.hang_counter = 0
                raise Exception('Invalid operand, command, or sequence')
                
            search = re.search('/0+[Ff]', code) #EEPROM error immediate response needed 
            if search:  
                self.hang_counter = 0  
                raise Exception('EEPROM error, contact manufacturer') 
                
            search = re.search('/0+[AaIiJj]', code)  #immediate response needed 
            if search:  
                self.hang_counter = 0  
                raise Exception('Initialisation/Overload error, examine pump, tubing and valve') 
                
            search = re.search('/0+[Gg]', code) #pump not initialised - will initialise the pump
            if search:
                time.sleep(0.1)
                print('Pump not initialised - now initialising pump')
                self.hang_counter = 0
                self.initialisePump(self)
            
        else: 
            self.hang_counter += 1
            print('No pump response - attempting again')
            self.readResponse()
        
    def volToIncr(self, vol):
        incr = int((self.resolution*vol)/self.syringe_size)
        return incr

    # initialise pump in clockwise direction - output valve is I=1 which is also default value
    def initialisePump(self):
        if self.readResponse() == '/0`':
            self.serialCom.write(bytearray('/1ZR\r\n', "ascii"))
            #double check how this will work when it initialises a full syringe
    
    # fill the input line an push excess to waste, then fill syringe and push to output with exact volume to fill output tube
    # need to test how well this works
    def primeReagent(self, reagentNum):
        if reagentNum == 1:
            inputPort = self.input1Port
            inputTubeVol = self.input1TubeVol
            outputPort = self.output1Port
            outputTubeVol = self.output1TubeVol
            self.reagent1Primed = True
        elif reagentNum == 2:
            inputPort = self.input2Port
            inputTubeVol = self.input2TubeVol
            outputPort = self.output2Port
            outputTubeVol = self.output2TubeVol
            self.reagent2Primed = True
        elif reagentNum == 3:
            inputPort = self.input3Port
            inputTubeVol = self.input3TubeVol
            outputPort = self.output3Port
            outputTubeVol = self.output3TubeVol
            self.reagent3Primed = True
        elif reagentNum == 4:
            inputPort = self.input4Port
            inputTubeVol = self.input4TubeVol
            outputPort = self.output4Port
            outputTubeVol = self.output4TubeVol
            self.reagent4Primed = True
        elif reagentNum == 5:
            inputPort = self.input5Port
            inputTubeVol = self.input5TubeVol
            outputPort = self.output5Port
            outputTubeVol = self.output5TubeVol
            self.reagent5Primed = True
        else:
            print('Reagent number is not valid')

        # pull syringe down by 2x the volume of the input tubing
        # push out to waste
        # input line should now be full of correct solvent -> this should all work if tubing is full of air or cleaning solvent.
        # pull down by volume needed to fill output tube
        # push out to output tube by precise volume needed.  

        inputIncrx2 = self.volToIncr(2*inputTubeVol)
        outputIncr = self.volToIncr(outputTubeVol)

        while self.readResponse() != '/0`':
            pass

        if self.readResponse() == '/0`':
            self.serialCom.write(bytearray(f'/1I{inputPort}A{inputIncrx2}I{self.wastePort}A0I{inputPort}A{outputIncr}I{outputPort}A0R\r\n', 'ascii'))

    # empties whatever is left in syringe into waste, then washes out the syringe twice with wash solvent into waste
    def washSyringe(self):
        if self.readResponse() == '/0`':
            self.serialCom.write(bytearray(f'/1I{self.wastePort}A0gI{self.washPort}A{self.resolution}I{self.wastePort}A0G2R\r\n', 'ascii'))

    # empties whatever is left in syringe into waste, washes out the syringe twice with the wash solvent, then switches to new reagent and pushes out 1 syringe worth to waste (should it be less than this?)
    def switchReagent(self, reagentNum): # for inputs, reagent number = reagent port 
        if self.readResponse() == '/0`':
            self.serialCom.write(bytearray(f'/1I{self.wastePort}A0gI{self.washPort}A{self.resolution}I{self.wastePort}A0G2I{reagentNum}A{self.resolution}I{self.wastePort}A0R\r\n', 'ascii'))
        # add in checks here for if the new reagent has been primed!  Maybe just warn the user and then prime it if it isn't primed?  Or warn user and ask them to do it manually?
        # or like a user input 'type 'y' to prime new reagent' kind of thing.  


    # dispenses target volume, vol, from source port valvePort.  vol must be given in mL
    def dispenseVol(self, reagentNum, vol):

        if reagentNum == 1:
            if self.reagent1Primed == True:      
                inputPort = self.input1Port
                inputTubeVol = self.input1TubeVol
                outputPort = self.output1Port
                outputTubeVol = self.output1TubeVol
            else:
                raise Exception('Reagent 1 has not been primed!')
        elif reagentNum == 2:
            if self.reagent2Primed == True:  
                inputPort = self.input2Port
                inputTubeVol = self.input2TubeVol
                outputPort = self.output2Port
                outputTubeVol = self.output2TubeVol
            else:
                raise Exception('Reagent 2 has not been primed!')
        elif reagentNum == 3:
            if self.reagent3Primed == True:  
                inputPort = self.input3Port
                inputTubeVol = self.input3TubeVol
                outputPort = self.output3Port
                outputTubeVol = self.output3TubeVol
            else:
                raise Exception('Reagent 3 has not been primed!')
        elif reagentNum == 4:
            if self.reagent4Primed == True:  
                inputPort = self.input4Port
                inputTubeVol = self.input4TubeVol
                outputPort = self.output4Port
                outputTubeVol = self.output4TubeVol
            else:
                raise Exception('Reagent 4 has not been primed!')
        elif reagentNum == 5:
            if self.reagent5Primed == True:  
                inputPort = self.input5Port
                inputTubeVol = self.input5TubeVol
                outputPort = self.output5Port
                outputTubeVol = self.output5TubeVol
            else:
                raise Exception('Reagent 5 has not been primed!')
        else:
            raise Exception('Reagent number is not valid')

        incr = self.volToIncr(vol)

        if incr <= 6000 and incr > 0:
            if self.readResponse() == '/0`':
                self.serialCom.write(bytearray(f'/1I{self.wastePort}A0I{inputPort}A{incr}I{outputPort}A0R\r\n', 'ascii'))
                # could add something so it only does the [wastePort, A0] if not alredy at A0...
        elif incr > 6000:
            # aspriate and dispense with full syringe length apart from last bit
            fullStrokes = incr//self.resolution # floor division
            remainderIncr = incr - (fullStrokes*self.resolution)
            if self.readResponse() == '/0`':
                self.serialCom.write(bytearray(f'/1I{self.wastePort}A0gI{inputPort}A{self.resolution}I{outputPort}A0G{fullStrokes}I{inputPort}A{remainderIncr}I{outputPort}A0R\r\n', 'ascii'))
        else:
            print('Dispense volume doesn\'t make sense - is it negative? 0? not a number?')


