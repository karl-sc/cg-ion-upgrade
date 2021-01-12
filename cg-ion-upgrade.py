#!/usr/bin/env python3
PROGRAM_NAME = "cg-ion-upgrade.py"
PROGRAM_DESCRIPTION = """
CloudGenix script to intelligently upgrade/downgrade ION firmware.
---------------------------------------

usage: cg-ion-upgrade.py 
  -h, --help            show this help message and exit
  --ion-serial ion-serial, -i ion-serial
                        The serial number of the ION to update
  --version-target "version-target", -v "version-target"
                        Target software version for upgrade/downgrade process
                        (Default: Highest current version)
  --token "MYTOKEN", -t "MYTOKEN"
                        specify an authtoken to use for CloudGenix
                        authentication
  --authtokenfile "MYTOKENFILE.TXT", -f "MYTOKENFILE.TXT"
                        a file containing the authtoken
  --action action, -a action
                        (upgrade | downgrade | auto) choose whether to upgrade or
                        downgrade firmware (Default:auto)
  --max-steps max-steps, -s max-steps
                        The maximum firmware steps to upgrade or downgrade
                        (default:5)
  --max-wait max-wait, -w max-wait
                        The maximum time to wait for each firmware change step
                        in seconds (default:240)

Upgrades or Downgrades an ION in stages based on the TAC recommended path. I.E. 4.5 -> 4.7 -> 5.0 -> 5.2
This script follows regex logic as python DICT's in upgrade_path_regex or downgrade_path_regex respectively

Example:

cg-ion-upgrade.py --ion-serial '11114d56-0000-b727-d7e8-f46f53aaaaaa'
    Upgrades this serial to the latest version using interactive auth

cg-ion-upgrade.py --ion-serial '11114d56-0000-b727-d7e8-f46f53aaaaaa' -v "5.2.7" -s 2
    Upgrades this serial to the latest 5.2.7 version, but perform no more than 2 firmware update steps for safety

cg-ion-upgrade.py --ion-serial '11114d56-0000-b727-d7e8-f46f53aaaaaa' -w 360 -a downgrade -v "4.5.3"
    Downgrade an ion to version 4.5.3 and wait 360 seconds (6 minutes) between each firmware downgrade step
"""

upgrade_path_regex = {    
    "4\.5\..*" : "4.7.1", ### 4.5.xyz -> 4.7.1
    "4\.7\..*" : "5.0.3", ### 4.7.xyz -> 5.0.3
    "5\.0\..*" : "5.2.7", ### 5.0.xyz -> 5.2.7
    "5\.1\..*" : "5.2.7", ### 5.1.xyz -> 5.2.7
    "5\.2\..*" : "5.4.3", ### 5.2.xyz -> 5.2.7
}

downgrade_path_regex = {
    "4\.7\..*" : "4.5.3", ### 4.7.xyz -> 4.5.3
    "5\.0\..*" : "4.7.1", ### 5.0 to 4.7.1
    "5\.1\..*" : "4.7.1", ### 5.1 to 4.7.1
    "5\.2\..*" : "5.0.3", ### 5.2 to 5.0.3
    "5\.4\..*" : "5.2.7", ### 5.4 to 5.2.7
}


from cloudgenix import API
import time
import re
import sys
import argparse


def parse_arguments():
    CLIARGS = {}
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=PROGRAM_DESCRIPTION
            )
    parser.add_argument('--ion-serial', '-i', metavar='ion-serial', type=str, 
                    help='The serial number of the ION to update', required=True)
    parser.add_argument('--version-target', '-v', metavar='"version-target"', type=str, 
                    help='Target software version for upgrade/downgrade process (Default: Highest current version)', default=None)
    parser.add_argument('--token', '-t', metavar='"MYTOKEN"', type=str, 
                    help='specify an authtoken to use for CloudGenix authentication')
    parser.add_argument('--authtokenfile', '-f', metavar='"MYTOKENFILE.TXT"', type=str, 
                    help='a file containing the authtoken')
    parser.add_argument('--action', '-a', metavar='action', type=str, 
                    help='(upgrade | downgrade | auto) choose whether to upgrade or downgrade firmware. Default: auto', default="auto", required=False)
    parser.add_argument('--max-steps', '-s', metavar='max-steps', type=str, 
                    help='The maximum firmware steps to upgrade or downgrade (default:5)', default="5", required=False)    
    parser.add_argument('--max-wait', '-w', metavar='max-wait', type=str, 
                    help='The maximum time to wait for each firmware change step in seconds (default:240)', default="240", required=False)    
                
    args = parser.parse_args()
    CLIARGS.update(vars(args)) ##ASSIGN ARGUMENTS to our DICT
    return(CLIARGS)

def authenticate(CLIARGS):
    print("AUTHENTICATING...")
    user_email = None
    user_password = None
    sdk = API()
    ##First attempt to use an AuthTOKEN if defined
    if CLIARGS['token']:                    #Check if AuthToken is in the CLI ARG
        CLOUDGENIX_AUTH_TOKEN = CLIARGS['token']
        print("    ","Authenticating using Auth-Token in from CLI ARGS")
    elif CLIARGS['authtokenfile']:          #Next: Check if an AuthToken file is used
        tokenfile = open(CLIARGS['authtokenfile'])
        CLOUDGENIX_AUTH_TOKEN = tokenfile.read().strip()
        print("    ","Authenticating using Auth-token from file",CLIARGS['authtokenfile'])
    elif "X_AUTH_TOKEN" in os.environ:              #Next: Check if an AuthToken is defined in the OS as X_AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
        print("    ","Authenticating using environment variable X_AUTH_TOKEN")
    elif "AUTH_TOKEN" in os.environ:                #Next: Check if an AuthToken is defined in the OS as AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
        print("    ","Authenticating using environment variable AUTH_TOKEN")
    else:                                           #Next: If we are not using an AUTH TOKEN, set it to NULL        
        CLOUDGENIX_AUTH_TOKEN = None
        print("    ","Authenticating using interactive login")
    ##ATTEMPT AUTHENTICATION
    if CLOUDGENIX_AUTH_TOKEN:
        sdk.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if sdk.tenant_id is None:
            print("    ","ERROR: AUTH_TOKEN login failure, please check token.")
            sys.exit()
    else:
        while sdk.tenant_id is None:
            sdk.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not sdk.tenant_id:
                user_email = None
                user_password = None            
    print("    ","SUCCESS: Authentication Complete")
    return sdk

### Pulls in a version number in the format of XX.YY.ZZssRR and returns the Major, Minor, and Micro versiono
def major_minor_micro(version):
    major, minor, micro = re.search('(\d+)\.(\d+)\.(\d+)', version).groups()
    return int(major), int(minor), int(micro)

### Returns the elements Software Version given the Element ID
def get_element_sw_version(sdk, element_id):
	result = sdk.get.elements(element_id)
	if result.cgx_status:
		return result.cgx_content.get("software_version",None)
	return None

### Returns a Dictionary containing the version number as keys with the element image data structure as the value
def get_images_list(sdk):
    result = sdk.get.element_images()
    if result.cgx_status:
        images = result.cgx_content.get("items", None)
    else:
        return None
    image_dict = {}
    for image in images:
	    image_dict[image['version']] = image
    return image_dict

### Gets software_state for an element_id, edits the image to the image_id specified, then puts the updated software state up performing a firmware upgrade on an element
def execute_upgrade(sdk, element_id, image_id):
    result = sdk.get.software_state(element_id)
    if not (result.cgx_status):
        print("Error getting software state of element")
        return False
    software_state_data = result.cgx_content
    software_state_data['image_id'] = str(image_id)
    print("Executing Firmware Change")
    result = sdk.put.software_state(element_id,software_state_data)
    if not (result.cgx_status):
        print("Error updating software state of element")
        return False
    return True

### Waits for a period of time for a given element_id to change to a target_version
def wait_for_upgade(sdk, target_version, element_id, max_wait = 240): ###version numbers must be exact. Max_wait is in seconds
    print("Waiting for firmware change for up to",max_wait,"seconds")
    sleep_interval = 10
    orig_max_wait = max_wait
    current_version = get_element_sw_version(sdk, element_id)
    while (current_version != target_version) and (max_wait > 0):
        print("...Waiting",max_wait,"seconds")
        time.sleep(sleep_interval)
        max_wait = max_wait - sleep_interval
        current_version = get_element_sw_version(sdk, element_id)
    if (current_version != target_version):
        print("Sleep timer expired waiting for device to perform upgrade")
        return False
    print("Firmware change completed after", (orig_max_wait - max_wait), "seconds")
    return True

### Returns an exact full image version number from an image_dict given a version in the form of X.Y.Z. I.E. translates from 5.2.7 to 5.2.7-b22
def get_exact_major_minor_micro(version, image_dict):
    for image_version in image_dict.keys():
        if str(version) in image_version:
            return image_version
    return None

### Perfoms the staged upgrade
def staged_upgrade(sdk, element_id, max_version=None,  max_wait=240, max_steps=5, step=0): ##set max version to NONE for latest
    step += 1
    if step > max_steps:
        print("Max upgrade steps reached. Aborting!")
        return False
    image_dict = get_images_list(sdk)
    current_version = get_element_sw_version(sdk,element_id)
    if not max_version:
        max_version = max(image_dict.keys(), key=major_minor_micro)
    exact_max_version = get_exact_major_minor_micro(max_version, image_dict)
    exact_version = None
    if current_version == max_version or current_version == exact_max_version:
        print("Currently at max version specified. Completed.")
        return False
    for version_num in image_dict.keys():
        if max_version in version_num:
            exact_version = version_num
    if not exact_version:
        print("Exact version not found in image repository")
        return False
    ###now loop through and stage until current version is exact version
    upgrade_version = None
    upgrade_image_id = None
    for path in upgrade_path_regex.keys():
        if re.match(path,current_version):
            upgrade_version = get_exact_major_minor_micro(upgrade_path_regex[path], image_dict)
            upgrade_image_id = image_dict[upgrade_version]['id']
    if upgrade_version and upgrade_image_id:
        print("Step",step,"Performing upgrade from",current_version,"to",upgrade_version,"   (Target Version:",exact_max_version,")")
        if not execute_upgrade(sdk,element_id,upgrade_image_id):
            return False
        if not wait_for_upgade(sdk,upgrade_version,element_id,max_wait=max_wait):
            return False
        staged_upgrade(sdk, element_id, max_version, max_wait=max_wait, step=step, max_steps=max_steps)
    else:
        print("Could not find next version number in list")
        return False
    current_version = get_element_sw_version(sdk,element_id)
    if step == 1: print("Completed Firmware change to version",current_version)

### Perfoms the staged upgrade
def staged_downgrade(sdk, element_id, max_version=None, max_wait=240, max_steps=5, step=0): ##set max version to NONE for latest
    step += 1
    if step > max_steps:
        print("Max upgrade steps reached. Aborting!")
        return False
    image_dict = get_images_list(sdk)
    current_version = get_element_sw_version(sdk,element_id)
    if not max_version:
        max_version = min(image_dict.keys(), key=major_minor_micro)
    exact_max_version = get_exact_major_minor_micro(max_version, image_dict)
    exact_version = None
    if current_version == max_version or current_version == exact_max_version:
        if step == 1: print("Currently at max version specified. Completed.")
        return False
    for version_num in image_dict.keys():
        if max_version in version_num:
            exact_version = version_num
    if not exact_version:
        print("Exact version not found in image repository")
        return False
    ###now loop through and stage until current version is exact version
    upgrade_version = None
    upgrade_image_id = None
    for path in downgrade_path_regex.keys():
        if re.match(path,current_version):
            upgrade_version = get_exact_major_minor_micro(downgrade_path_regex[path], image_dict)
            upgrade_image_id = image_dict[upgrade_version]['id']
    if upgrade_version and upgrade_image_id:
        print("Step",step,"Performing DOWNGRADE from",current_version,"to",upgrade_version,"   (Target Version:",exact_max_version,")")
        if not execute_upgrade(sdk,element_id,upgrade_image_id):
            return False
        if not wait_for_upgade(sdk,upgrade_version,element_id, max_wait=max_wait):
            return False
        staged_downgrade(sdk, element_id, max_version, max_wait=max_wait, step=step,  max_steps=max_steps)
    else:
        print("Could not find next version number in list")
        return False
    current_version = get_element_sw_version(sdk,element_id)
    if step == 1: print("Completed Firmware change to version",current_version)


def find_ion_by_sn(sdk, ion_serial): 
    result = sdk.get.elements()
    if not (result.cgx_status):
        print("Error getting a list of IONS")
        return False
    element_list = result.cgx_content.get("items", None)
    for element in element_list:
        if element['hw_id'] == str(ion_serial):
            return element['id']
    print("Could not find ION serial",str(ion_serial),"in tenant")
    return False

def is_upgrade_or_downgrade(sdk, element_id, target_version):
    image_dict = get_images_list(sdk)
    current_version = get_element_sw_version(sdk,element_id)
    if not target_version:
        target_version = max(image_dict.keys(), key=major_minor_micro)
    exact_target_version = get_exact_major_minor_micro(target_version, image_dict)
    (target_major, target_minor, target_micro) = major_minor_micro(exact_target_version)
    (current_major, current_minor, current_micro) = major_minor_micro(current_version)
    # First compare major versions to check for upgrade or downgrade
    if current_major < target_major:
        return "upgrade"
    if current_major > target_major:
        return "downgrade"
    # Since major versions are equal, check minor version
    if current_minor < target_minor:
        return "upgrade"
    if current_minor > target_minor:
        return "downgrade"
    # Since minor versions are equal, check micro version, but remove all except from digits for our comparison
    current_minor = re.sub('\D', '', str(current_minor))
    target_minor = re.sub('\D', '', str(target_minor))
    if current_minor < target_minor:
        return "upgrade"
    if current_minor > target_minor:
        return "downgrade"
    print("Aborting. Version numbers are the same")
    return None
    

def go(sdk, CLIARGS):
    ion_serial = str(CLIARGS['ion_serial'])
    cli_action = str(CLIARGS['action'])
    max_steps = int(CLIARGS['max_steps'])
    max_wait = int(CLIARGS['max_wait'])
    version_target = CLIARGS['version_target']
    element_id = find_ion_by_sn(sdk,ion_serial)
    action = is_upgrade_or_downgrade(sdk, element_id,version_target )
    if not action:
        print("Could not determine if this is an upgrade or downgrade")
        return False  
    if (cli_action != "auto") and (cli_action != action):
        print("Error. Action was specified to be",cli_action,"but we detected that the firmware change to be " + str(action) + ". Either double check the intended action/target version, or set to Auto")
        return False
    if (cli_action == "auto"):
        print("current version number compared to target indicates",action)
    if not element_id:
        return False
    if action == "upgrade":
        staged_upgrade(sdk, element_id, max_version=version_target, max_steps=max_steps, max_wait=max_wait)
    elif action == "downgrade":
        staged_downgrade(sdk, element_id, max_version=version_target, max_steps=max_steps, max_wait=max_wait)
    else:
        print("Unknown Action. Must be either upgrade or downgrade")
        return False
        
def logout(sdk):
    print("Logging out")
    sdk.get.logout()

if __name__ == "__main__":
    CLIARGS = parse_arguments()
    sdk = authenticate(CLIARGS)
    if sdk: go(sdk,CLIARGS)
    logout(sdk)
