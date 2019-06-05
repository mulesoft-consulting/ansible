#!/usr/bin/python

# Copyright: (c) 2019, Gonzalo Camino <gonzalo.camino@mulesoft.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ap_account_environment

short_description: Create or Delete Environment on Account

version_added: "2.8"

description:
    - "This module supports basic operations for create or delete environments on Anypoint Platform Accounts"

options:
    name:
        description:
            - Environment name
        required: true
    state:
        description:
            - Assert the state of the environment. Use C(present) to create an environment and C(absent) to delete it.
        required: true
        choices: [ "present", "absent" ]
    bearer:
        description:
            - Anypoint Platform access token for an active session
        required: true
    host:
        description:
            - The host of your Anypoint Platform Installation
        required: false
        default: anypoint.mulesoft.com
    organization:
        description:
            - Anypoint Platform Organization Name to work on
        required: true
    type:
        description:
            - Environment type
        choices: [ "design", "sandbox", "production" ]
        default: production
        required: false

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
    - anypoint-cli
'''

EXAMPLES = '''
# Example of creating a Production Environment
- name: Create the Production Environment
  ap_account_environment:
    name: 'Production'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    host: 'anypoint.mulesoft.com
    organization: 'My Demos'

# Example of creating a Development Environment
- name: Create the Development Environment
  ap_account_environment:
    name: 'Development'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    type: 'sandbox'

# Example of creating a deleting an Environment
- name: Delete the Development Environment
  ap_account_environment:
    name: 'Development'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
'''

RETURN = '''
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def do_no_action(module):
    return_value = False
    environment_exists = False
    cmd = get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --host="' + module.params['host'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' account environment list --output json'

    result = module.run_command(cmd)

    if result[0] != 0:
        module.fail_json(msg=result[1])

    resp_json = json.loads(result[1])
    # check if the environment exists
    for item in resp_json:
        if (item['Name'] == module.params['name']):
            environment_exists = True
            break

    if (module.params['state'] == "absent"):
        return_value = not environment_exists
    elif (module.params['state'] == "present"):
        return_value = environment_exists

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        type=dict(type='str', required=False, default="production", choices=["design", "sandbox", "production"])
    )

    result = dict(
        changed=False,
        msg='No action taken'
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Main Module Logic
    # first all check that the anypoint-cli binary is present on the host
    if (get_anypointcli_path(module) is None):
        module.fail_json(msg="anypoint-cli binary not present on host")

    # exit if the execution is in check_mode
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    if (do_no_action(module) is True):
        module.exit_json(**result)

    cmd = get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' --host="' + module.params['organization'] + '"'
    cmd += ' account environment'
    cmd_base = cmd

    # Parameters set action
    if module.params['state'] == "present":
        cmd += ' create --type ' + module.params['type']
    elif module.params['state'] == "absent":
        cmd += ' delete'

    cmd += ' "' + module.params['name'] + '"'
    output = module.run_command(cmd)

    if output[0] != 0:
        module.exit_json(msg=output[1])
    else:
        result['msg'] = output[1]
        result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
