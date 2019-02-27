#!/usr/bin/env python2.7

import os
import pdb
import sys
import select
import prlsdkapi
from prlsdkapi import *


from pprint import pprint


def dump(obj):
  for attr in dir(obj):
    print("obj.%s = %r" % (attr, getattr(obj, attr)))

# Initialize the SDK.
def init():
    #print "init_server_sdk"
    prlsdkapi.init_server_sdk()


# Deinitialize the SDK.
def deinit():
    print "deinit_sdk"
    prlsdkapi.deinit_sdk()


# Create a Virtuozzo Container.
def create(srv, name, os_template):
    print 'create ct'
    ct = srv.create_vm()
    ct.set_vm_type(consts.PVT_VM)
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
#################
def get_hdd_info(vm):
    # Obtain the VmConfig object containing the virtual server
    # configuration information.
    vm_config = vm.get_config()
    count = vm_config.get_hard_disks_count()
    vm_hdds_info = []
    for d in range(count):
        hdd = vm_config.get_hard_disk(d)
        emulated_type = hdd.get_emulated_type()

        if emulated_type == consts.PDT_USE_REAL_DEVICE:
            hdd_emulated_type_inf = {"boot_camp": hdd.get_friendly_name()}
        elif emulated_type == consts.PDT_USE_IMAGE_FILE:
            hdd_emulated_type_inf = {"image_file": hdd.get_image_path()}
        else:
            hdd_emulated_type_inf = "UNKNOWN"

        if hdd.get_disk_type() == consts.PHD_EXPANDING_HARD_DISK:
            hdd_type_inf = "expanding_disk"
        elif hdd.get_disk_type() == consts.PHD_PLAIN_HARD_DISK:
            hdd_type_inf = "plain_disk"
        else:
            hdd_type_inf = "UNKNOWN"
        # Disk size in Mbytes
        hdd_info = {"hdd_number": d, "size": hdd.get_disk_size(), "size_on_ph_drive": hdd.get_size_on_disk(),
                    "hdd_emulated_type": hdd_emulated_type_inf, "hdd_type": hdd_type_inf}
        vm_hdds_info.append(hdd_info)
    return vm_hdds_info


def get_net_adapter_info(vm):
    # Obtain the VmConfig object containing the virtual server
    # configuration information.
    vm_config = vm.get_config()
    # Obtain the network interface info.
    # The vm.net_adapters sequence contains objects of type VmNetDev.
    count = vm_config.get_net_adapters_count()
    vm_net_adapter_info = []
    for n in range(count):
        net_adapter = vm_config.get_net_adapter(n)
        emulated_type = net_adapter.get_emulated_type()

        if emulated_type == consts.PNA_HOST_ONLY:
            n_emulated_type = "host-only"
        elif emulated_type == consts.PNA_SHARED:
            n_emulated_type = "shared"
        elif emulated_type == consts.PNA_BRIDGED_ETHERNET:
            n_emulated_type = {"bridged": net_adapter.get_bound_adapter_name()}
        else:
            n_emulated_type = "UNKNOWN"
        #n_type = net_adapter.get_iface_type()
        n_type = ""
        n_gateway = net_adapter.get_default_gateway()
        n_name = net_adapter.get_bound_adapter_name()

        n_ip = ""
        n_mac_address = str(net_adapter.get_mac_address())
        net_adapter_info = {"net_adapter": n, "emulated_type": n_emulated_type, "mac_address": n_mac_address,
                            "type": n_type, "gateway": n_gateway, "name": n_name, "ip": n_ip}
        vm_net_adapter_info.append(net_adapter_info)
    return vm_net_adapter_info

###
def get_vm_os_info(vm):

 print("\n-----------------------------")
 # Virtual server name.
 print("Virtual server name: " + vm.get_name())

 # Obtain the VmConfig object containing the virtual server
 # configuration information.
 vm_config = vm.get_config()
 # Obtain the guest OS type and version.
 # OS types are defined as PVS_GUEST_TYPE_xxx constants.
 # For the complete list, see the documentation for
 # the prlsdkapi.prlsdk.consts module or
 # the Virtuozzo Python API Reference guide.
 os_type = vm_config.get_os_type()
 if os_type == consts.PVS_GUEST_TYPE_WINDOWS:
     osType = "Windows"
 elif os_type == consts.PVS_GUEST_TYPE_LINUX:
     osType = "Linux"
 else:
     osType = "Other type (" + str(os_type) + ")"

 # OS versions are defined as PVS_GUEST_VER_xxx constants.
 os_version = vm_config.get_os_version()
 if os_version == consts.PVS_GUEST_VER_WIN_WINDOWS8:
     osVersion = "Windows 8"
 elif os_version == consts.PVS_GUEST_VER_LIN_CENTOS:
     osVersion = "CentOS"
 else:
     osVersion = "Other version (" + str(os_version) + ")"
# print "Guest OS: " + osType + " " + osVersionRAM size
# p.115 - 130 !!!!!!!!!!


###
def get_vm_info():
    init()
    server = prlsdkapi.Server()
    #server.login_local().wait()
    server.login('127.0.0.1', 'user', 'passwd_with_sudo_priv').wait()
# Obtain the prlsdkapi.ServerConfig object.
# The object contains the host server configuration information.
    job_vm_list = server.get_vm_list_ex(consts.PVTF_VM | consts.PVTF_CT)
    #job_vm_list = server.get_vm_list()  # returns just a list of VM
    job_vm_list.wait()
    result = job_vm_list.get_result()
    members_info = {}
    # Iterate through the Result object parameters.
    # Each parameter is an instance of the prlsdkapi.Vm class.
    for i in range(result.get_params_count()):
        member = result.get_param_by_index(i)
        # Obtain the prlsdkapi.VmConfig object containing the virtual server
        # configuration information.
        member_config = member.get_config()
        # Get the name of the virtual server.
        params = {"get_name": 'get_name()'}
        #for param in params:
        member_name = member_config.get_name()
        member_os = member_config.get_os_type()
        member_hostname = member_config.get_hostname()
        member_description = member_config.get_description()
        member_cpu_count = member_config.get_cpu_count()
        member_ram = member_config.get_ram_size()
        member_auto_start = member_config.get_auto_start()
        member_vnc = member_config.get_vncmode()
        member_hdd = get_hdd_info(member)
        member_net_adapters = get_net_adapter_info(member)
        member_dns_raw = member_config.get_dns_servers()
        member_search_domains_raw = member_config.get_search_domains()
        member_search_domains = []
        member_dns = []
        for d in member_dns_raw:
            member_dns.append(d)
        for s in member_search_domains_raw:
            member_search_domains.append(s)
        # CPU usage limit (in percent) for a virtual machine.
        #member_cpu_limit = member_config.get_cpu_limit()
        # Determine the number of CPU units allocated to a virtual machine.
        member_cpu_units = member_config.get_cpu_units()
        member_type = member_config.get_vm_type()
        member_is_template = member_config.is_template()
        # member_gateway = member_config.get_default_gateway()

        if member_type == consts.PVT_VM:
            member_type_is = "VM"
        elif member_type == consts.PVT_CT:
            member_type_is = "CT"
        else:
            member_type_is = "UNKNOWN"
        # p. 91 *_api_reference.*
        member_info = {"hostname": member_hostname, "description": member_description, "cpu_count": member_cpu_count,
                       "ram": member_ram, "auto_start": member_auto_start, "type": member_type_is,
                       "template": member_is_template, "vnc": member_vnc, "search_domains": member_search_domains,
                       "hdd": member_hdd, "dns": member_dns, "net_adapters": member_net_adapters, "os": member_os}
        members_info.update({member_name: member_info})
    for name, details in members_info.items():
        print("\nname: {0}\n{1}\n***************************************************".format(name, details))
    # try:
    #     result = server.get_srv_config().wait()
    #     print(result)
    # except prlsdkapi.PrlSDKError, e:
    #     print("Error: {}".format(e))
    #
    # srv_config = result.get_param()
    # print(srv_config)

# Create a new prlsdkapi.Vm object.
#     vm = server.create_vm()
#
# # Set the virtual server type (PVT_VM - Virtual Machine;  PVT_CT - Container)
#     vm.set_vm_type(consts.PVT_VM)
#
# # Use the default configuration for the Virtual Machine.
# # Parameters of the set_default_config method:
# # param_1: The host server configuration object.
# # param_2: Target OS type and version.
# # param_3: Specifies to create the virtual server devices using
# # default values (the settings can be modified
# # later if needed).
# # centOS: PVS_GUEST_VER_LIN_CENTOS
# # Windows8: PVS_GUEST_VER_WIN_WINDOWS8
# #     if srv_config is None or srv_config == "":
# #         print("\n * 'srv_config' is empty!\n")
# #         sys.exit(1)
# #     else:
#     vm.set_default_config(srv_config, consts.PVS_GUEST_VER_LIN_CENTOS, True)
#
# # Set the virtual server name and description.
#     vm.set_name(vm_name)
#     vm.set_description(vm_description)
#
# # Modify the default RAM size and HDD size.
# # These two steps are optional. If you omit them, the
# # default values will be used.
# # vm_ram_size  in MB
#     vm.set_ram_size(vm_ram_size)
#
# # Set HDD size to 10 gig.
# # The get_device method obtains a prlsdkapi.VmHardDisk object.
# # The index 0 is used because the default configuration has a
# # single hard disk.
# # vm_hdd_size in MB
#     dev_hdd = vm.get_hard_disk(0)
#     dev_hdd.set_disk_size(vm_hdd_size)
#
# # Register the virtual server with the Virtuozzo host.
# # The first parameter specifies to create the server in the
# # default directory on the host computer.
# # The second parameter specifies that non-interactive mode
# # should be used.
#     print "Creating a virtual server..."
#     try:
#         vm.reg("", True).wait()
#     except prlsdkapi.PrlSDKError, e:
#         print("Error: {}".format(e))
#         return
#     print "Virtual server was created successfully."


# ##############
# ### Create a Virtual Machine ###
# def create(server):
#     # Get the ServerConfig object.
#     result = server.get_srv_config().wait()
#     srv_config = result.get_param()
#     # Create a Vm object and set the virtual server type
#     # to Virtual Machine (PVT_VM).
#     vm = server.create_vm()
#     vm.set_vm_type(consts.PVT_VM)
#     # Set a default configuration for the VM.
#     vm.set_default_config(srv_config, consts.PVS_GUEST_VER_WIN_WINDOWS8, True)
#     # Set the VM name.
#     vm.set_name("Windows8")
#     # Modify the default RAM and HDD size.
#     vm.set_ram_size(2048)
#     dev_hdd = vm.get_hard_disk(0)
#     dev_hdd.set_disk_size(10000)
#     # Register the VM with the Virtuozzo.
#     vm.reg("", True).wait()
#
# # Change VM name.
# def setName(vm, name):
#     print 'set_name'
#     vm.begin_edit().wait()
#     vm.set_name(name)
#     vm.commit().wait()

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


if __name__ == "__main__":
    get_vm_info()
