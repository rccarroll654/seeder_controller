#!/usr/bin/python
#
# motor_control_gui.py
#

import os, time, random
import sys, traceback
import itertools
import serial
import Tkinter
import tkMessageBox, tkFileDialog
import threading

from seeder_controller import SeederController

class gui_interface():
  def __init__(self):
    self.title = "Seeder Motor Controller V2.0"
    self.tb = None
    self.OM_port = None
    self.disable = False
    self.logo_path = "CE_logo.gif"
    self.modulation_list = ["Narrow Band","Wide Band"]
    self.stream_file = ""
    self.locked = False
    self.th = None

  def t_print(self,string,T=None):
    if not T:
      T = self.T_CS
    T.config(state=Tkinter.NORMAL)
    T.delete(1.0,Tkinter.END)
    T.insert(Tkinter.INSERT,string)
    T.config(state=Tkinter.DISABLED)
    T.update()
    self.top.update()

  def quit_gui(self,other=None):
    self.top.withdraw()
    self.top.destroy()
    del self.top

  def about_dialog(self):
    ad = Tkinter.Tk()
    ad.title('About')

    msg = self.title
    msg += '\n\nWritten by: \n\nRussell Carroll\nrussell_carroll@carrelec.com'
    msg += '\nCarroll Electronics\nCopyright 2018'

    L_about = Tkinter.Label(ad, text=msg, width=30, 
                                height=9, justify=Tkinter.LEFT)
    L_about.grid(row=0,column=0)


  def freeze_controls(self,freeze=True):
    # Regular buttons
    objects = [self.B_mp,self.B_mb,self.B_setr]
    for o in objects:
      if freeze:
        o.config(state=Tkinter.DISABLED)
      else:
        o.config(state=Tkinter.NORMAL)
    # STOP button
    if freeze:
        self.B_stop.config(state=Tkinter.NORMAL)
    else:
        self.B_stop.config(state=Tkinter.DISABLED)
    self.top.update()

  def guiRunMotor(self):
    try:
      self.freeze_controls()
      self.sc.log("\nCall to guiRunMotor\n")
      # Get parameters
      motor_id = int(self.Mtr_string.get().split()[1])
      steps = int(float(self.E_step_text.get()))
      direction = self.dir_string.get()
      speed = int(float(self.E_speed_text.get()))
      style = self.style_string.get()
      
      # Run command
      self.sc.runStepper(motor_id,steps=steps,direction=direction,speed=speed,style=style)
    except:
      self.sc.log("\n  -- Error\n")
      self.sc.log(traceback.format_exc())
    finally:
      self.freeze_controls(freeze=False)

  def guiSetRelay(self):
    try:
      self.freeze_controls()
      self.sc.log("\nCall to guiSetRelay\n")
      # Get parameters
      relay = int(float(self.relay_string.get().split()[2]))
      mode = self.mode_string.get()
      
      # Run command
      self.sc.setRelay(relay,mode=mode)
      time.sleep(0.5)
    except:
      self.sc.log("\n  -- Error\n")
      self.sc.log(traceback.format_exc())
    finally:
      self.freeze_controls(freeze=False)

  def guiMainProcessLoop(self):
    try:
      self.freeze_controls()
      self.sc.log("\nCall to guiMainProcessLoop\n")
      # Get option
      option = int(self.option_string.get().split('.')[0])
      # Lookup command
      if option == 1:
        cmd = self.sc.runOption1
      elif option == 2:
        cmd = self.sc.runOption2
      elif option == 3:
        cmd = self.sc.runOption3
      elif option == 4:
        cmd = self.sc.runOption4
      elif option == 5:
        cmd = self.sc.runOption5
      else:
        self.sc.log("\n  -- Error (Unknown Option)\n")
        raise ValueError
      self.process_thread = threading.Thread(target=cmd) 
      self.process_thread.start()
      while self.process_thread.isAlive():
          self.top.update()
    except:
      self.sc.log("\n  -- Error\n")
      self.sc.log(traceback.format_exc())
    finally:
      self.freeze_controls(freeze=False)

  def guiStopProcess(self):
    self.sc.stop = True
    self.sc.releaseAll()

  def run_GUI(self):
    # GUI
    top = Tkinter.Tk()
    self.top = top
    top.title(self.title)
    top.resizable(width=False, height=False)
    top["bg"] = "grey"
    menubar = Tkinter.Menu(top)

    # File
    filemenu = Tkinter.Menu(menubar, tearoff=0)
    filemenu.add_command(label="Exit", command=self.quit_gui)
    menubar.add_cascade(label="File", menu=filemenu)

    helpmenu = Tkinter.Menu(menubar, tearoff=0)
    helpmenu.add_command(label="About", command=self.about_dialog)
    menubar.add_cascade(label="Help", menu=helpmenu)
    self.menubar = menubar

    # display the menu
    top.config(menu=menubar)

    W1 = 10
    W2 = 15
    W3 = 5

    self.W1 = W1
    self.W2 = W2
    self.W3 = W3

    # Give space around top
    Sstart = Tkinter.Label(top, text=' ', width=W1)
    Sstart.grid(row=0,column=0)
    Sstart["bg"] = "grey"

    # Give space around top
    Smid = Tkinter.Label(top, text=' ', width=W1)
    Smid.grid(row=1,column=3)
    Smid["bg"] = "grey"

    # Motor
    L_mtr = Tkinter.Label(top, text='Motor  ', justify=Tkinter.RIGHT)
    L_mtr.grid(row=1,column=1,sticky=Tkinter.E)
    L_mtr["bg"] = "grey"
    Mtr_string = Tkinter.StringVar()
    self.Mtr_string = Mtr_string
    motor_id = [
        "Motor 1 (Conveyor)",
        "Motor 2 (Hopper)",
        "Motor 3 (Clean Tray)",
        "Motor 4 (Seedhead)"
    ]
    Mtr_port = Tkinter.OptionMenu(self.top, self.Mtr_string, *tuple(motor_id))
    #Mtr_port.config(width=6, bd=0)
    Mtr_port.grid(row=1,column=2,sticky=Tkinter.W)
    #OM_port["bg"] = "grey"
    self.Mtr_port = Mtr_port
    self.Mtr_string.set(motor_id[0])
    sv = self.Mtr_string

    # Steps
    S_steps = Tkinter.Label(top, text=' ', width=W1)
    S_steps.grid(row=2,column=1)
    S_steps["bg"] = "grey"
    
    L_step = Tkinter.Label(top, text='Steps  ', justify=Tkinter.RIGHT)
    L_step.grid(row=3,column=1,sticky=Tkinter.E)
    L_step["bg"] = "grey"
    E_step_text = Tkinter.StringVar()
    E_step = Tkinter.Entry(top,bd=2, width=10, textvariable=E_step_text)
    E_step.grid(row=3,column=2,sticky=Tkinter.W)
    E_step_text.set('100')
    #E_freq["bg"] = "grey"
    self.E_step = E_step
    self.E_step_text = E_step_text

    # Direction
    S_dir = Tkinter.Label(top, text=' ', width=W1)
    S_dir.grid(row=4,column=1)
    S_dir["bg"] = "grey"
    
    L_dir = Tkinter.Label(top, text='Direction  ', justify=Tkinter.RIGHT)
    L_dir.grid(row=5,column=1,sticky=Tkinter.E)
    L_dir["bg"] = "grey"
    dir_string = Tkinter.StringVar()
    self.dir_string = dir_string
    dir_options = ["Forward","Reverse"]
    dir_port = Tkinter.OptionMenu(self.top, self.dir_string, *tuple(dir_options))
    dir_port.config(width=6, bd=0)
    dir_port.grid(row=5,column=2,sticky=Tkinter.W)
    #OM_port["bg"] = "grey"
    self.dir_port = dir_port
    self.dir_string.set(dir_options[0])
    
    # Speed
    S_speed = Tkinter.Label(top, text=' ', width=W1)
    S_speed.grid(row=6,column=1)
    S_speed["bg"] = "grey"
    
    L_speed = Tkinter.Label(top, text='Speed (RPM)  ', justify=Tkinter.RIGHT)
    L_speed.grid(row=7,column=1,sticky=Tkinter.E)
    L_speed["bg"] = "grey"
    E_speed_text = Tkinter.StringVar()
    E_speed = Tkinter.Entry(top,bd=2, width=10, textvariable=E_speed_text)
    E_speed.grid(row=7,column=2,sticky=Tkinter.W)
    E_speed_text.set('20')
    #E_freq["bg"] = "grey"
    self.E_speed = E_speed
    self.E_speed_text = E_speed_text
    
    # Style
    S_style = Tkinter.Label(top, text=' ', width=W1)
    S_style.grid(row=8,column=1)
    S_style["bg"] = "grey"
    
    L_style = Tkinter.Label(top, text='Style  ', justify=Tkinter.RIGHT)
    L_style.grid(row=9,column=1,sticky=Tkinter.E)
    L_style["bg"] = "grey"
    style_string = Tkinter.StringVar()
    self.style_string = style_string
    style_list = ["Double","Single","Interleave","Microstep"]
    style_port = Tkinter.OptionMenu(self.top, self.style_string, *tuple(style_list))
    style_port.config(width=6, bd=0)
    style_port.grid(row=9,column=2,sticky=Tkinter.W)
    #OM_port["bg"] = "grey"
    self.style_port = style_port
    self.style_string.set(style_list[0])
    sv = self.style_string


    # Run Motor Button
    S_mb = Tkinter.Label(top, text=' ', width=W1)
    S_mb.grid(row=10,column=1)
    S_mb["bg"] = "grey"
    
    B_mb = Tkinter.Button(top, text=' Run Stepper ', bd=2, command=self.guiRunMotor)
    B_mb.grid(row=11,column=2,sticky=Tkinter.W)
    self.B_mb = B_mb

    # Seed Rows
    L_row = Tkinter.Label(top, text=' Option  ', justify=Tkinter.RIGHT)
    L_row.grid(row=1,column=4,sticky=Tkinter.E)
    L_row["bg"] = "grey"
    E_row_text = Tkinter.StringVar()
    E_row = Tkinter.Entry(top,bd=2, width=6, textvariable=E_row_text)
    E_row.grid(row=1,column=5,sticky=Tkinter.W)
    E_row_text.set('29')
    
    option_string = Tkinter.StringVar()
    self.option_string = option_string
    mode_options = ["1. Dibble and Seed 29 Rows",
                    "2. Dibble and Seed 12 Rows",
                    "3. Seed 12 Rows, No Dibble",
                    "4. No Dibble, Place 3 Seeds Over 12 Rows",
                    "5. Dibble 12 Rows, Places 2 Seeds Per Row"
                    ]
    option_port = Tkinter.OptionMenu(self.top, self.option_string, 
            *tuple(mode_options))
    option_port.config(width=40, bd=0)
    option_port.grid(row=1,column=5,sticky=Tkinter.W)
    #OM_port["bg"] = "grey"
    self.option_port = option_port
    self.option_string.set(mode_options[0])

    # Main Program Loop
    B_mp = Tkinter.Button(top, text=' START ', bd=2, bg="green",
            command=self.guiMainProcessLoop)
    B_mp.grid(row=3,column=5,sticky=Tkinter.W)
    self.B_mp = B_mp

    # Stop button
    B_stop = Tkinter.Button(top, text=' STOP ', bd=2, bg="red", fg="white",
            command=self.guiStopProcess)
    B_stop.grid(row=5,column=5,sticky=Tkinter.W)
    self.B_stop = B_stop
    self.B_stop.config(state=Tkinter.DISABLED)

    # Relay
    L_relay = Tkinter.Label(top, text='Relay  ', justify=Tkinter.RIGHT)
    L_relay.grid(row=9,column=4,sticky=Tkinter.E)
    L_relay["bg"] = "grey"
    relay_string = Tkinter.StringVar()
    self.relay_string = relay_string
    relay_list = [
        "Relay Channel 1 pin set to 14 (Dibbler)",
        "Relay Channel 2 pin set to 15 (Needle Vacuum)",
        "Relay Channel 3 pin set to 18 (Needle Air)",
        "Relay Channel 4 pin set to 23 (Spare)",
        "Relay Channel 5 pin set to 24 (Vibrate seed)",
        "Relay Channel 6 pin set to 17 (Vibrate Hopper)",
        "Relay Channel 7 pin set to 27 (Activate Vacuum)",
        "Relay Channel 8 pin set to 22 (Hopper Auger)"]
    relay_port = Tkinter.OptionMenu(self.top, self.relay_string, *tuple(relay_list))
    #relay_port.config(width=6, bd=0)
    relay_port.grid(row=9,column=5,sticky=Tkinter.W)
    #OM_port["bg"] = "grey"
    self.relay_port = relay_port
    self.relay_string.set(relay_list[0])

    # Mode
    L_mode = Tkinter.Label(top, text='Mode  ', justify=Tkinter.RIGHT)
    L_mode.grid(row=11,column=4,sticky=Tkinter.E)
    L_mode["bg"] = "grey"
    mode_string = Tkinter.StringVar()
    self.mode_string = mode_string
    mode_list = ["Open","Close"]
    mode_port = Tkinter.OptionMenu(self.top, self.mode_string, *tuple(mode_list))
    mode_port.config(width=6, bd=0)
    mode_port.grid(row=11,column=5,sticky=Tkinter.W)
    #OM_port["bg"] = "grey"
    self.mode_port = mode_port
    self.mode_string.set(mode_list[0])

    L_s = Tkinter.Label(top, text=' ', justify=Tkinter.RIGHT)
    L_s.grid(row=12,column=4,sticky=Tkinter.E)
    L_s["bg"] = "grey"
    
    # Set Relay
    B_setr = Tkinter.Button(top, text=' Set Relay ', bd=2, command=self.guiSetRelay)
    B_setr.grid(row=13,column=5,sticky=Tkinter.W)
    self.B_setr = B_setr
    
    #T_CS["bg"] = "grey"
    Send = Tkinter.Label(top, text=' ', width=W3)
    Send.grid(row=100,column=100)
    Send["bg"] = "grey"
    

    
    # update
    if self.sc:
        self.sc.refresh = self.top.update
    
    top.mainloop()


if __name__ == "__main__":
  gui = gui_interface()
  sc = SeederController()
  sc.num_rows = 3
  gui.sc = sc
  gui.run_GUI()
