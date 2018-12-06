#!/usr/bin/env python2.7

import os
import select
import prlsdkapi
from prlsdkapi import consts


# Initialize the SDK.
def init():
    print "init_server_sdk"
    prlsdkapi.init_server_sdk()


# Deinitialize the SDK.
def deinit():
    print "deinit_sdk"
    prlsdkapi.deinit_sdk()
    

# Create a Virtuozzo Container.
def create(srv, name, os_template):
    print 'create ct'
    ct = srv.create_vm()
    ct.set_vm_type(consts.PVT_CT)
    ct.set_name(name)
    ct.set_os_template(os_template)
    ct.reg('', True).wait()
    return ct


# Register a Container with Virtuozzo
def register(srv, path):
    print 'register ct'
    ct = srv.register_vm(path).wait()
    return ct


# Change a Container name.
def setName(ct, name):
    print 'set_name'
    ct.begin_edit().wait()
    ct.set_name(name)
    ct.commit().wait()


# Set CPU limits for a Container.
def setCpuLimit(ct, limit):
    print 'set_cpu_limit'
    ct.begin_edit().wait()
    ct.set_cpu_limit(limit)
    ct.commit().wait()


# Set RAM size for a Container.
def setRamSize(ct, size):
    print 'set_ram_size'
    ct.begin_edit().wait()
    ct.set_ram_size(size)
    ct.commit().wait()


# Add a hard disk to a Container.
def addHdd(ct, image, size):
    print 'add hdd'
    ct.begin_edit().wait()
    hdd = ct.create_vm_dev(consts.PDE_HARD_DISK)
    hdd.set_emulated_type(consts.PDT_USE_IMAGE_FILE)
    hdd.set_disk_type(consts.PHD_EXPANDING_HARD_DISK)
    hdd.set_disk_size(size)
    hdd.set_enabled(True)
    hdd.create_image(bRecreateIsAllowed=True, bNonInteractiveMode=True).wait()
    ct.commit().wait()
    

# Execute a program in a Container.
def execute(ct, cmd, args):
    print 'execute command'
    io = prlsdkapi.VmIO()
    io.connect_to_vm(ct, consts.PDCT_HIGH_QUALITY_WITHOUT_COMPRESSION).wait()

    # open guest session
    result = ct.login_in_guest('root', '').wait()
    guest_session = result.get_param()

    # format args and envs
    sdkargs = prlsdkapi.StringList()
    for arg in args:
        sdkargs.add_item(arg)
    sdkargs.add_item("")
    sdkenvs = prlsdkapi.StringList()
    sdkenvs.add_item("")

    # execute
    ifd, ofd = os.pipe()
    flags = consts.PRPM_RUN_PROGRAM_ENTER|consts.PFD_STDOUT
    job = guest_session.run_program(cmd, sdkargs, sdkenvs,
    nFlags = flags, nStdout = ofd)

    # read output
    output = ''
    while True:
        rfds, _, _ = select.select([ifd], [], [], 5)
        if not rfds:
            break
        buf = os.read(ifd, 256)
        output += buf
    print('output:\n%s--end of output' % output)

    # cleanup
    os.close(ifd)
    job.wait()
    guest_session.logout()
    io.disconnect_from_vm(ct)


### CT create ###
def create_ct(ct_name, ct_os_template, ct_cpu_limit, ct_ram):
    init()
    srv = prlsdkapi.Server()
    srv.login_local().wait()
    # Create and start a Container.
    ct = create(srv, ct_name, ct_os_template)
    ct.start().wait()
    # Execute the '/bin/cat /proc/cpuinfo' command in the Container.
    execute(ct, '/bin/cat', ['/proc/cpuinfo'])
    ct.stop().wait()
    # Set some parameters and add a hard disk to the Container.
    setCpuLimit(ct, ct_cpu_limit)
    # Set RAM in MB
    setRamSize(ct, ct_ram)

    # ??????
    addHdd(ct, '/tmp/my_empty_hdd_image', 1024)
    srv.logoff().wait()
    deinit()

    # Clone a Container.
    ct2 = ct.clone('121', '').wait().get_param()
    print('Clone name = %s' % ct2.get_name())
    # Unregister and registers back a Container.
    home_path = ct.get_home_path()
    ct.unreg()
    ct = srv.register_vm(home_path).wait().get_param()
    # Delete a Container.
    ct.delete()
    ct2.delete()
    srv.logoff().wait()
    deinit()


### Create a Virtual Machine ###
def create(server):
    # Get the ServerConfig object.
    result = server.get_srv_config().wait()
    srv_config = result.get_param()
    # Create a Vm object and set the virtual server type
    # to Virtual Machine (PVT_VM).
    vm = server.create_vm()
    vm.set_vm_type(consts.PVT_VM)
    # Set a default configuration for the VM.
    vm.set_default_config(srv_config, consts.PVS_GUEST_VER_WIN_WINDOWS8, True)
    # Set the VM name.
    vm.set_name("Windows8")
    # Modify the default RAM and HDD size.
    vm.set_ram_size(256)
    dev_hdd = vm.get_hard_disk(0)
    dev_hdd.set_disk_size(3000)
    # Register the VM with the Virtuozzo.
    vm.reg("", True).wait()

# Change VM name.
def setName(vm, name):
    print 'set_name'
    vm.begin_edit().wait()
    vm.set_name(name)
    vm.commit().wait()

# Set boot device priority
def vm_boot_priority(vm):
    # Begin the virtual server editing operation.
    vm.begin_edit().wait()
    # Modify boot device priority using the following order: CD > HDD > Network > FDD.
    # Remove all other devices from the boot priority list (if any).
    count = vm.get_boot_dev_count()
    for i in range(count):
        boot_dev = vm.get_boot_dev(i)
        # Enable the device.
        boot_dev.set_in_use(True)
        # Set the device sequence index.
        dev_type = boot_dev.get_type()
        if dev_type == consts.PDE_OPTICAL_DISK:
            boot_dev.set_sequence_index(0)
        elif dev_type == consts.PDE_HARD_DISK:
            boot_dev.set_sequence_index(1)
        elif dev_type == consts.PDE_GENERIC_NETWORK_ADAPTER:
            boot_dev.set_sequence_index(2)
        elif dev_type == consts.PDE_FLOPPY_DISK:
            boot_dev.set_sequence_index(3)
        else:
            boot_dev.remove()
    # Commit the changes.
    vm.commit().wait()


# Execute a program in a VM.
def execute(vm):
    # Log in.
    g_login = "Administrator"
    g_password = "12345"
    # Create a StringList object to hold the program input parameters and populate it.
    hArgsList = prlsdkapi.StringList()
    hArgsList.add_item("cmd.exe")
    hArgsList.add_item(" / C")
    hArgsList.add_item("C:\\123.bat")
    # Create an empty StringList object.
    # The object is passed to the VmGuest.run_program method and
    # is used to specify the list of environment variables and
    # their values to add to the program execution environment.
    # In this sample, we are not adding any variables.
    # If you wish to add a variable, add it in the var_name=var_value format.
    hEnvsList = prlsdkapi.StringList()
    hEnvsList.add_item("")
    # Establish a user session.
    vm_guest = vm.login_in_guest(g_login, g_password).wait().get_param()
    # Run the program.
    vm_guest.run_program("cmd.exe", hArgsList, hEnvsList).wait()
    # Log out.
    vm_guest.logout().wait()


### MAIN ###

if __name__ == "__main__":
    create_ct("py_test1", 'centos-7-x86_64', 50, 1024)