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
module: ap_exchange_asset_page

short_description: Manage the Page of an Asset on Exchange

version_added: "2.8"

description:
    - "This module supports upload, modify and delete assets pages on Exchange"

options:
    name:
        description:
            - Asset page name. Naming the page [home] makes the uploaded page the main description page for the Exchange asset
    state:
        description:
            - Assert the state of the page. Use Use C(present) to create a page and C(absent) to delete it.
        required: true
        choices: [ "present", absent" ]
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
    group_id:
        description:
            - The assets groupId
        required: true
    asset_id:
        description:
            - The assets assetId
        required: true
    asset_version:
        description:
            - The assets version
        required: false
        default: 1.0.0
    md_path:
        description:
            - Path to the markdown page file

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - anypoint-cli
'''

EXAMPLES = '''
# Example of setting exchange asset main page
- name: Upload Exchange Page
  ap_exchange_asset_page:
    name: 'home'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
    md_path: '/tmp/home.md'

# Example of deleting exchange asset main page
- name: Upload Exchange Page
  ap_exchange_asset_page:
    name: 'home'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
'''

RETURN = '''
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import json
import fileinput
import re
from ansible.module_utils.basic import AnsibleModule


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def get_asset_identifier(group_id, asset_id, asset_version):
    return group_id + '/' + asset_id + '/' + asset_version


def execute_anypoint_command(module, action, other_args):
    asset_identifier = get_asset_identifier(module.params['group_id'], module.params['asset_id'], module.params['asset_version'])
    cmd = get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --host="' + module.params['host'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' exchange asset page ' + action + ' --output json "' + asset_identifier + '"' + other_args

    output = module.run_command(cmd)

    if output[0] != 0:
        module.fail_json(msg='[execute_anypoint_command] ' + output[1])

    return output[1]


def do_no_action(module):
    return_value = False
    page_exists = False

    output = execute_anypoint_command(module, 'list', '')

    cleaned_result = output.replace('Getting asset pages list', '')
    if (len(cleaned_result) > 2):
        resp_json = json.loads(cleaned_result)
        # check if the asset's page exists
        for item in resp_json:
            if (item['Name'] == module.params['name']):
                page_exists = True

    if (module.params['state'] == "present"):
        # always upload content
        return_value = False
    elif (module.params['state'] == "absent"):
        return_value = not page_exists

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        group_id=dict(type='str', required=True),
        asset_id=dict(type='str', required=True),
        asset_version=dict(type='str', required=False, default="1.0.0"),
        md_path=dict(type='str', required=False, default=None)
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

    # validations pre check_mode
    if (module.params['state'] == 'present') and (module.params['md_path'] is None):
        module.fail_json(msg="present state requires 'md_path' argument")

    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if environment exists
    if (do_no_action(module) is True):
        module.exit_json(**result)

    other_args = ' ' + module.params['name']
    if (module.params['state'] == 'present'):
        action = 'upload'
        other_args += ' ' + module.params['md_path']
    elif (module.params['state'] == 'absent'):
        action = 'delete'

    output = execute_anypoint_command(module, action, other_args)

    result['msg'] = output
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
