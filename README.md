# cg-ion-upgrade
CloudGenix script to intelligently upgrade/downgrade ION firmware.


```
# usage: cg-ion-upgrade.py 
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
                        (upgrade | downgrade) choose whether to upgrade or
                        downgrade firmware
  --max-steps max-steps, -s max-steps
                        The maximum firmware steps to upgrade or downgrade
                        (default:5)
  --max-wait max-wait, -w max-wait
                        The maximum time to wait for each firmware change step
                        in seconds (default:240)
```
Upgrades or Downgrades an ION in stages based on the TAC recommended path. I.E. 4.5 -> 4.7 -> 5.0 -> 5.2
This script follows regex logic as python DICT's in upgrade_path_regex or downgrade_path_regex respectively

# Examples:

cg-ion-upgrade.py --ion-serial '11114d56-0000-b727-d7e8-f46f53aaaaaa'
    Upgrades this serial to the latest version using interactive auth

cg-ion-upgrade.py --ion-serial '11114d56-0000-b727-d7e8-f46f53aaaaaa' -v "5.2.7" -s 2
    Upgrades this serial to the latest 5.2.7 version, but perform no more than 2 firmware update steps for safety

cg-ion-upgrade.py --ion-serial '11114d56-0000-b727-d7e8-f46f53aaaaaa' -w 360 -a downgrade -v "4.5.3"
    Downgrade an ion to version 4.5.3 and wait 360 seconds (6 minutes) between each firmware downgrade step
