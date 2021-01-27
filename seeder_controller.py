#!/usr/bin/python
# -*- coding: utf-8 -*-
"""This module is the interface library used to control the seeding machine
developed by Keith Haynes.

See the Seeder-Code-Interface-Specification.pdf for brief design description.

Written for Python 2.7. Four spaces per indentation.

Written by Russell Carroll.
Email: russell_carroll@carrelec.com
"""

from Adafruit_MotorHAT import (Adafruit_MotorHAT, Adafruit_DCMotor,
                                Adafruit_StepperMotor)
from time import sleep, time
import atexit
import threading
import random
import RPi.GPIO as GPIO

"""
Empty classes for Adafruit_MotorHAT module.
-> Used only if the MotorHAT module is not installed.
"""
class Adafruit_MotorHAT_empty():
    def __init__(self,addr):
        self.addr = addr
        self.RELEASE = 0
        
    def getMotor(self,mtr):
        return self
    
    def getStepper(self,steps_per_rev,port):
        return Adafruit_StepperMotor_empty()
    
    def setSpeed(self,speed):
        pass
    
    def run(self,mode):
        pass

class Adafruit_DCMotor_empty(Adafruit_MotorHAT):
    def __init__(self):
        pass
        
class Adafruit_StepperMotor_empty(Adafruit_MotorHAT):
    def __init__(self):
        pass
        
    def step(self, numsteps, direction, style):
        pass

class SeederController():
    """Seeder controller object.

    Used to call the individual commands needed to run the seeder without
    having to worry about hardware details.
    """

    """
    ----------------------------------
     Miscellaneous functions
    ----------------------------------
    """
    def __init__(self, config_fn="seeder_config.txt"):
        # Default values
        self.log_text       = ""
        self.log_fn         = "seeder_log.txt"
        self.verbose        = True
        self.num_rows       = 29        # Number of seeder rows
        self.stop           = False
        # MotorHAT addresses
        self.bothat_addr    = 0x60
        self.midhat_addr    = 0x61      # Not used
        self.tophat_addr    = 0x63      # Not used
        # Relay Channel GPIO Pins
        self.relay_list     = [1, 2, 3, 4, 5, 6, 7, 8]
        
        self.Relay_Ch       = {}    # Defines GPIO pins used by relay
        self.Relay_Ch[1]    = 14
        self.Relay_Ch[2]    = 15
        self.Relay_Ch[3]    = 18
        self.Relay_Ch[4]    = 23
        self.Relay_Ch[5]    = 24
        self.Relay_Ch[6]    = 17
        self.Relay_Ch[7]    = 27
        self.Relay_Ch[8]    = 22

        # Stepper Motor
        self.motor_id       = [ 1,    2,    3,    4   ]
        self.motor_control  = [ "GP", "GP", "GP", "GP"] # GP=GPIO, MH=MotorHAT
        self.steps_per_rev  = [ 200,  200,  200,  200 ] 
        self.motor_port     = [ 0,    0,    0,    0   ] # Used by MotorHAT only
        self.motor_speed    = [ 25,   25,   25,   25  ]
        self.dir_pin        = [ 19,   20,   13,   8   ] # Used by GPIO only
        self.step_pin       = [ 26,   21,   6,    25  ] # Used by GPIO only
        self.gpio_cw        = [ 1,    1,    1,    1   ] # Used by GPIO only
        self.gpio_ccw       = [ 0,    0,    0,    0   ]
        
        # Thread queue
        self.thread_queue = []

        # Startup procedure
        self.log("-- Keith Haynes Seeder Controller --", mode='w')
        self.log("\nSeeder Controller Startup...\n")
        GPIO.setmode(GPIO.BCM)  # Setup GPIO
        GPIO.setwarnings(False)
        self.setupMotorHAT()
        self.setupMotors()
        self.setupRelays()

    def __del__(self):
        # Final shutdown procedure
        try:
            self.turnOffMotors()
        except:
            pass
            
        try:
            GPIO.cleanup()
        except:
            pass
            
        # Save log file
        try:
            fh = open(self.log_fn, 'w')
            fh.write(self.log_text)
            fh.close()
        except IOError:
            print("  Warning: Failed to save {}".format(self.log_fn))

    # Logging function
    def log(self, text_str, log_only=False, mode='a'):
        if self.verbose and not log_only:
            print(text_str)
        self.log_text += text_str + '\n'
        try:
            fh = open(self.log_fn, mode)
            fh.write(text_str + '\n')
            fh.close()
        except IOError:
            if not log_only:
                print("  Warning: Failed to save {}".format(self.log_fn))

    # refresh command for multi threading
    def refresh(self):
        pass

    """
    ----------------------------------
     Low Level Functions
    ----------------------------------
    """
    # Define MotorHAT interfaces
    def setupMotorHAT(self):
        msg_text = "  Bottom HAT addr set to " + hex(self.bothat_addr)
        self.log(msg_text,log_only=True)
        try:
            self.bothat = Adafruit_MotorHAT(addr=self.bothat_addr)
        except:
            self.log("\tWarning: Adafruit_MotorHAT Initialization Failure.",log_only=True)
            self.bothat = Adafruit_MotorHAT_empty(addr=self.bothat_addr)
    
    # Function to find counter clockwise polarity
    def getCCW(self, cw):
        if cw == 1:
            return 0
        else:
            return 1
    
    def setupGPIOmotor(self, mtr, dir_pin, step_pin):
        msg = "  Defining GPIO motor: "
        msg += "motor_id={}, dir_pin={}, step_pin={}"
        msg = msg.format(   self.motor_id[mtr],
                            dir_pin,
                            step_pin   )
        self.log(msg,log_only=True)
        # set pins
        GPIO.setup(dir_pin,  GPIO.OUT)
        GPIO.setup(step_pin, GPIO.OUT)
        GPIO.output(dir_pin, self.gpio_cw[mtr])

    # Define motors
    def setupMotors(self):
        # MotorHAT
        self.stepper = {}
        for mtr in range(len(self.motor_id)):
            if self.motor_control[mtr] == "GP":
                self.setupGPIOmotor(mtr, self.dir_pin[mtr], self.step_pin[mtr])
            elif self.motor_control[mtr] == "MH":
                msg = "  Defining MotorHAT motor: "
                msg += "motor_id={}, steps_per_rev={}, motor_port={}"
                msg = msg.format(   self.motor_id[mtr],
                                    self.steps_per_rev[mtr],
                                    self.motor_port[mtr] )
                self.log(msg,log_only=True)
                self.stepper[self.motor_id[mtr]] = self.bothat.getStepper(
                        self.steps_per_rev[mtr], self.motor_port[mtr] )
                self.stepper[self.motor_id[mtr]].setSpeed(
                                                    self.motor_speed[mtr])

    def getIndex(self, motor_id):
        return self.motor_id.index(motor_id)   # Get motor index from id

    def setSpeed(self, motor_id, speed=0):
        if speed > 0:
            msg = "  Setting speed of motor {} to {}".format(motor_id, speed)
            self.log(msg, log_only=True)
            mtr_index = self.getIndex(motor_id)
            self.motor_speed[mtr_index] = speed 
            if self.motor_control[mtr_index] == "MH":
                self.stepper[motor_id].setSpeed(speed)

    # Define GPIO pins for relays
    def setupRelays(self):
        for relay in self.relay_list:
            msg_text = "  Relay Channel {} pin set to {}".format(relay,self.Relay_Ch[relay])
            self.log(msg_text,log_only=True)
            GPIO.setup(self.Relay_Ch[relay],GPIO.OUT)
            GPIO.output(self.Relay_Ch[relay],GPIO.HIGH)
    
    # Turn off all motors
    def turnOffMotors(self):
        for mtr in range(4):
            self.bothat.getMotor(mtr+1).run(Adafruit_MotorHAT.RELEASE)

    def checkStop(self):
        if self.stop:
            self.log("  Stop signal detected")
            raise RuntimeError

    """ Sets relay to a given state.
    
    >>> self.setRelay(1,"ON")   # Turn relay 1 on
    None                        # Returns nothing
    """
    def setRelay(self,relay,mode="on"):
        self.checkStop()
        if relay in self.relay_list:
            pin = self.Relay_Ch[relay]
        else:
            self.log("  Unknown relay: {}".format(relay))
            raise ValueError
        
        msg = "  Relay {} set {}".format(relay,mode)
        self.log(msg,log_only=True)
        
        cmd = mode.lower()
        if ("on" in cmd) or ("close" in cmd):
            GPIO.output(self.Relay_Ch[relay],GPIO.LOW)     # LOW = ON/Closed
        elif ("off" in cmd) or ("open" in cmd):
            GPIO.output(self.Relay_Ch[relay],GPIO.HIGH)    # HIGH = OFF/Open
        else:
            self.log("  Unknown mode: {}".format(mode))
            raise ValueError

    def getDirectionCode(self, direction):
        code = None
        if "for" in direction.lower():
            code = Adafruit_MotorHAT.FORWARD
        elif "rev" in direction.lower():
            code = Adafruit_MotorHAT.BACKWARD
        return code


    def getStyleCode(self, style):
        code = None
        cmd = style.lower()
        if "double" in cmd:
            code = Adafruit_MotorHAT.DOUBLE
        elif "single" in cmd:
            code = Adafruit_MotorHAT.SINGLE
        elif "interleave" in cmd:
            code = Adafruit_MotorHAT.INTERLEAVE
        elif "micro" in cmd:
            code = Adafruit_MotorHAT.MICROSTEP
        return code

    # MotorHAT stepper worker function
    def stepper_worker(self, motor_id, numsteps, direction, style):
        # Check direction
        if direction == Adafruit_MotorHAT.FORWARD:
            this_dir = "Forward"
        elif direction == Adafruit_MotorHAT.BACKWARD:
            this_dir = "Reverse"
        else:
            raise ValueError
        
        # Check style
        if style == Adafruit_MotorHAT.DOUBLE:
            this_style = "Double"
        elif style == Adafruit_MotorHAT.SINGLE:
            this_style = "Single"
        elif style == Adafruit_MotorHAT.INTERLEAVE:
            this_style = "Interleave"
        elif style  == Adafruit_MotorHAT.MICROSTEP:
            this_style = "Microstep"
        else:
            raise ValueError
        
        msg = "  Starting MotorHAT stepper worker: "
        msg += "motor_id={}, numsteps={}, direction={}, style={}"
        msg = msg.format(motor_id, numsteps, this_dir, this_style)
        self.log(msg, log_only=True)
        
        # Run the stepper
        self.stepper[motor_id].step(numsteps, direction, style)
        
        msg =  "  Finished MotorHAT stepper worker: "
        msg += "motor_id={}".format(motor_id)
        self.log(msg, log_only=True)

    def runGPIO_Stepper(self, motor_id, steps, direction="Forward"):
        mtr_index = self.getIndex(motor_id)
        dir_low = direction.lower()
        cw = self.gpio_cw[mtr_index]
        if ('rev' in dir_low) or ('ccw' in dir_low):
            dir_code = self.getCCW(cw)
        else:
            dir_code = cw
        
        # Calculate the delay from speed
        spr = self.steps_per_rev[mtr_index]
        rpm = self.motor_speed[mtr_index]
        delay = 30.0/(spr*rpm)   # Warning: Some limits should be made on this

        msg = "  Starting GPIO stepper worker: "
        msg += "motor_id={}, numsteps={}, direction={}"
        msg = msg.format(motor_id, steps, direction)
        self.log(msg, log_only=True)
        
        # Set direction
        GPIO.output(self.dir_pin[mtr_index], dir_code)
        
        # Run stepper motor. Use absolute timing for better accuracy
        next_time = time() 
        for x in range(steps):
            self.checkStop()
            GPIO.output(self.step_pin[mtr_index], GPIO.HIGH)
            next_time += delay
            while time() < next_time:
                sleep(delay/10)
            
            GPIO.output(self.step_pin[mtr_index], GPIO.LOW)
            next_time += delay
            while time() < next_time:
                sleep(delay/10)
        
        msg =  "  Finished GPIO stepper worker: "
        msg += "motor_id={}".format(motor_id)
        self.log(msg, log_only=True)
    
    def releaseStepper(self,motor_id):
        mtr_index = self.getIndex(motor_id)
        if self.motor_control[mtr_index] == "GP":
            pass    # do nothing, TODO - check with Keith
        elif self.motor_control[mtr_index] == "MH":
            port = self.motor_port[mtr_index]
            self.bothat.getMotor(port).run(Adafruit_MotorHAT.RELEASE)
    
    def runStepper(self,motor_id, steps=0, direction="Forward", 
                                            style="Double",
                                            speed=0):
        self.checkStop()
        if steps == 0:
            self.log("  Warning: Call to runStepper() but steps = 0")
            return  # Do nothing
        self.setSpeed(motor_id,speed)   # update speed if provided
        mtr_index = self.getIndex(motor_id)
        if self.motor_control[mtr_index] == "GP":
            self.runGPIO_Stepper(motor_id,steps,direction)
        elif self.motor_control[mtr_index] == "MH":
            dir_code = self.getDirectionCode(direction)
            style_code = self.getStyleCode(style)
            self.stepper_worker(motor_id, steps, dir_code, style_code)

    """ (Not Ready - Do not use) 
    Enables stepper without blocking. (Multiple motors can run at once)
    
    # Step motor 3 by 100 steps in the forward direction
    >>> self.startStepperNoBlock(3,steps=100) 
    
    # Step motor 2 by 45 steps in the reverse direction
    >>> self.startStepperNoBlock(2,steps=45,direction="Reverse") 
    """ 
    def startStepperNoBlock(self,motor_id, steps=0, direction="Forward", 
                                            style="Double",
                                            speed=0):
        self.checkStop()
        msg = "  Starting motor {} as non-blocking."
        args = (motor_id, steps, direction, style, speed)
        this_thread = threading.Thread(target=self.runStepper, args=args) 
        self.thread_queue.append(this_thread)
        this_thread.start()

    # Waits for all motors to finish
    def waitForMotors(self):
        msg = "  Waiting for {} motor threads to finish."
        self.log(msg.format(len(self.thread_queue)) ,log_only=True)
        while len(self.thread_queue) > 0:
            self.refresh()
            if self.thread_queue[-1]:
                if not self.thread_queue[-1].isAlive():
                    del self.thread_queue[-1]
            else:
                del self.thread_queue[-1]   # remove from list
        self.log("  Threads finished.",log_only=True)
    
    """
    ----------------------------------
     User Level Functions
    ----------------------------------
    """
    def releaseAll(self):
        self.log("\nRelease Motors")
        self.turnOffMotors()
        self.releaseAirValves()
        self.setRelay(1,mode="Close")
        self.log("\nPlease wait...")
        sleep(0.1)
        
    def fillTray(self, steps_m1_first=575, steps_m1=2850, steps_m2=8050):
        self.log("\nFill tray")
        self.setRelay(8,mode="Close")
        self.runStepper(1,steps=steps_m1_first,direction="Forward",speed=60)
        self.setRelay(6,mode="Close")
        # Run both at once\
        self.startStepperNoBlock(1,steps=steps_m1,direction="Forward",speed=10)   
        self.startStepperNoBlock(2,steps=steps_m2,direction="Forward",speed=70)   
        self.waitForMotors()
        self.setRelay(8,mode="Open")
        self.setRelay(6,mode="Open")
        
    def releaseDirtHopper(self):
        pass # No longer needed

    def cleanTray(self,steps_m1=3900,steps_m3=1900):
        self.log("Clean Tray")
        self.runStepper(1,steps=1,direction="Forward",speed=20)  
        # Run both at once 
        self.startStepperNoBlock(1,steps=steps_m1,direction="Forward",speed=40)   
        self.startStepperNoBlock(3,steps=steps_m3,direction="Forward",speed=50)  
        self.waitForMotors()
        self.releaseStepper(3)

    def setTray(self,steps_m1_fwd=1500,steps_m1_rvs=75):
        self.log("Set Tray")
        self.setRelay(1,mode="Close")
        sleep(0.1)
        self.runStepper(1,steps=steps_m1_fwd,direction="Forward",speed=160)
        self.runStepper(1,steps=steps_m1_rvs,direction="Reverse",speed=160)
        sleep(0.1)

    def forwardDibbler(self,steps_m1=190):
        self.log("Forward Dibbler")
        self.setRelay(1,mode="Open")
        sleep(0.1)
        self.runStepper(1,steps=steps_m1,direction="Forward",speed=160)

    def dippleRow(self, cnt, steps_odd=182, steps_even=182):
        self.log("\nDibble Row {}".format(cnt))
        self.setRelay(1,mode="Close")
        sleep(0.05)
        self.setRelay(1,mode="Open")
        sleep(0.05)
        if cnt%2 > 0:
            steps = steps_odd  # Odd rows
        else:
            steps = steps_even  # Even rows
        self.runStepper(1,steps=steps,direction="Forward",speed=160)
        
    def advanceToSeeder(self,steps_m1=403,steps_m4=219,dir_m4="Reverse"):
        self.log("\nAdvance To Seeder")
        self.log("Activate Vacuum")
        self.setRelay(7,mode="Close")        
        self.runStepper(1, steps=steps_m1, direction="Forward", speed=160)
        self.runStepper(4, steps=steps_m4, direction=dir_m4, style="Interleave")
               
    def activateVacuum(self):        
        self.setRelay(5,mode="Close")
        self.setRelay(2,mode="Close")
        self.setRelay(3,mode="Open")
        sleep(1.0)
        
    def setRow(self, cnt, steps_odd=182, steps_even=182):
        self.log("\nSet Row {}".format(cnt))
        if cnt%2 > 0:
            steps = steps_odd  # Odd rows
        else:
            steps = steps_even  # Even rows
        self.runStepper(1,steps=steps,direction="Forward")
        
    def rotateToTray(self,steps_m4=486, m4_dir="Forward"):
        self.log("Rotate To Tray")
        self.setRelay(5,mode="Open")
        sleep(0.5)
        self.setRelay(5,mode="Close")
        self.runStepper(4, steps=steps_m4, direction=m4_dir, speed=180,
                                                        style="Interleave")

    def releaseSeed(self,row,steps_nom=486,steps_last=372):
        self.log("Release Seed")
        self.setRelay(2,mode="Open")
        sleep(0.5)
        self.setRelay(3,mode="Close")
        sleep(0.05)
        self.setRelay(3,mode="Open")
        
        if row == self.num_rows:
            # Do not pick up another seed
            self.runStepper(4, steps=steps_last, direction="Reverse", speed=180, 
                                                    style="Interleave")
        else:
            # pick up another seed
            self.runStepper(4, steps=steps_nom, direction="Forward", speed=180, 
                                                    style="Interleave")
        self.setRelay(2,mode="Close")
        sleep(0.5)

    def returnToZero(self,steps_m1=4000):
        self.setRelay(5,mode="Open")        
        self.log("\nReturn To Zero")
        self.releaseStepper(4)
        self.runStepper(1, steps=steps_m1, direction="Forward", speed=160)
        self.releaseStepper(3)
        self.releaseStepper(4)
        
    def releaseAirValves(self):
        self.log("\nRelease Air Valves")
        for relay in self.relay_list:
            self.setRelay(relay,mode="Open")    # open all relays
        
    # Option 1. Dibble and Seed 29 Rows
    def runOption1(self):
        self.stop = False
        self.log("\n-- Begining Option 1 process loop --")
        self.num_rows = 29
        
        self.releaseAll()
        sleep(1.0)
        self.fillTray(steps_m1_first=5, steps_m1=5, steps_m2=5) 
        self.releaseDirtHopper()  
        self.cleanTray(steps_m1=3,steps_m3=1)   
        self.setTray(steps_m1_fwd=3,steps_m1_rvs=5) 
        self.forwardDibbler(steps_m1=9)

        for row in range(self.num_rows):        
            self.dippleRow(row+1,steps_odd=1, steps_even=1)

        self.advanceToSeeder(steps_m1=2000,steps_m4=170,dir_m4="Forward")
        self.activateVacuum()
        
        for row in range(self.num_rows):
            self.setRow(row+1, steps_odd=182, steps_even=182)
            self.rotateToTray(steps_m4=330, m4_dir="Reverse")   
            self.releaseSeed(row+1,steps_nom=330,steps_last=160)

        self.returnToZero(steps_m1=2500)    
        self.releaseAll()  
        
        self.log("\n-- End of Option 1 process loop --")

    # Option 2. Dibble and Seed 12 Rows
    def runOption2(self):
        self.stop = False
        self.log("\n-- Begining Option 2 process loop --")
        self.num_rows = 12
        
        self.releaseAll()
        sleep(10.0)
        self.fillTray(steps_m1_first=740, steps_m1=2375, steps_m2=17500) 
        self.releaseDirtHopper()  
        self.cleanTray(steps_m1=3300,steps_m3=1700)   
        self.setTray(steps_m1_fwd=2000,steps_m1_rvs=75) 
        self.forwardDibbler(steps_m1=234)

        for row in range(self.num_rows):        
            self.dippleRow(row+1,steps_odd=202, steps_even=204)

        self.advanceToSeeder(steps_m1=387,steps_m4=220)
        self.activateVacuum()               
        
        for row in range(self.num_rows):
            self.setRow(row+1, steps_odd=201, steps_even=203)
            self.rotateToTray(steps_m4=486)   
            self.releaseSeed(row+1,steps_nom=486,steps_last=275)

        self.returnToZero(steps_m1=2000)    
        self.releaseAll()    
        
        self.log("\n-- End of Option 2 process loop --")

    # Option 3. Seed 12 Rows, No Dibble
    def runOption3(self):
        self.stop = False
        self.log("\n-- Begining Option 3 process loop --")
        self.num_rows = 12
        
        self.releaseAll()
        sleep(10.0)
        self.fillTray(steps_m1_first=700, steps_m1=2475, steps_m2=8800) 
        self.releaseDirtHopper()  
        self.cleanTray(steps_m1=3200,steps_m3=1750)   
        self.setTray(steps_m1_fwd=2000,steps_m1_rvs=75) 
        self.forwardDibbler(steps_m1=2780)

        self.advanceToSeeder(steps_m1=390,steps_m4=220)
        self.activateVacuum()               
        
        for row in range(self.num_rows):
            self.setRow(row+1, steps_odd=212, steps_even=212)
            self.rotateToTray(steps_m4=486)   
            self.releaseSeed(row+1,steps_nom=486,steps_last=352)

        self.returnToZero(steps_m1=2000)    
        self.releaseAll()    
        
        self.log("\n-- End of Option 3 process loop --")

    # Option 4. No Dibble, Place 3 Seeds Over 12 Rows
    def runOption4(self):
        self.stop = False
        self.log("\n-- Begining Option 4 process loop --")
        self.num_rows = 12
        
        self.releaseAll()
        sleep(10.0)
        self.fillTray(steps_m1_first=740, steps_m1=2700, steps_m2=20000) 
        self.releaseDirtHopper()  
        self.cleanTray(steps_m1=3400,steps_m3=1400)   
        self.setTray(steps_m1_fwd=2000,steps_m1_rvs=75) 
        self.forwardDibbler(steps_m1=2720)

        self.advanceToSeeder(steps_m1=400,steps_m4=220)
        self.activateVacuum()                           
        
        for row in range(self.num_rows):
            # First Seed
            self.setRow(row+1, steps_odd=197, steps_even=197)
            self.rotateToTray(steps_m4=488)   
            self.releaseSeed(row,steps_nom=488,steps_last=352)
            # Second Seed
            self.runStepper(1,steps=5,direction="Forward")
            self.rotateToTray(steps_m4=488)   
            self.releaseSeed(row,steps_nom=488,steps_last=372)
            # Third Seed
            self.runStepper(1,steps=5,direction="Forward")
            self.rotateToTray(steps_m4=488)   
            self.releaseSeed(row+1,steps_nom=488,steps_last=285)

        self.returnToZero(steps_m1=500)    
        self.releaseAll()    
        self.log("\n-- End of Option 4 process loop --")

    # Option 5. Dibble 12 Rows, Places 2 Seeds Per Row
    def runOption5(self):
        self.stop = False
        self.log("\n-- Begining Option 5 process loop --")
        self.num_rows = 12
        
        self.releaseAll()
        sleep(10.0)
        self.fillTray(steps_m1_first=740, steps_m1=2575, steps_m2=15800) 
        self.releaseDirtHopper()  
        self.cleanTray(steps_m1=3400,steps_m3=1400)
        self.setTray(steps_m1_fwd=2000,steps_m1_rvs=75) 
        self.forwardDibbler(steps_m1=235)

        for row in range(self.num_rows):        
            self.dippleRow(row+1,steps_odd=205, steps_even=205)

        self.advanceToSeeder(steps_m1=387,steps_m4=220)
        self.activateVacuum()                       
        
        for row in range(self.num_rows):
            # First seed
            self.setRow(row+1, steps_odd=205, steps_even=205)
            self.rotateToTray(steps_m4=486)   
            self.releaseSeed(row,steps_nom=486,steps_last=275)
            # Second seed
            self.runStepper(1,steps=6,direction="Forward")
            self.rotateToTray(steps_m4=486)   
            self.releaseSeed(row+1,steps_nom=486,steps_last=275)

        self.returnToZero(steps_m1=200)    
        self.releaseAll()      
        
        self.log("\n-- End of Option 5 process loop --")


if __name__ == "__main__":
    # Create seeder controller object and run the main loop
    sc = SeederController()
    sc.num_rows = 3
    sc.runOption1()
