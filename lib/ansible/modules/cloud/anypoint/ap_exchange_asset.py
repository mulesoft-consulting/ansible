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
module: ap_exchange_asset

short_description: Manage an Asset on Exchange

version_added: "2.8"

description:
    - "This module supports upload, modify and delete assets on Exchange"

options:
    name:
        description:
            - Asset page name. Naming the page [home] makes the uploaded page the main description page for the Exchange asset
    state:
        description:
            - Assert the state of the page. Use C(present) to create an asset undeprecated, C(deprecated) toi deprecate it and C(absent) to delete it.
        required: true
        choices: [ "present", "deprecated", "absent" ]
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
    organization_id:
        description:
            - Anypoint Platform Organization Id to work on. Required for C(present) and C(deprecated) states
        required: false
    type:
        description:
            - The asset type
        required: true
        choices: [ "custom", "oas", "wsdl" ]
    group_id:
        description:
            - The asset groupId
        required: true
    asset_id:
        description:
            - The asset assetId
        required: true
    asset_version:
        description:
            - The asset version
        required: false
        default: 1.0.0
    api_version:
        description:
            - The asset version
        required: false
        default: 1.0.0
    main_file:
        description:
            - Main file of the API asset.
        type: path
        required: false
    file_path:
        description:
            - Path to the asset file. Required for C(present)
            - If points to a ZIP archive file, that archive must include an C(exchange.json) file describing the asset
        type: path
        required: false
    tags:
        description:
            - A list of tags for the asset
        required: false

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - anypoint-cli
'''

EXAMPLES = '''
# Example of uploading an exchange
- name: Upload Exchange Asset
  ap_exchange_asset:
    name: 'My Asset'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    type: 'custom'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
    main_file: '/tmp/custom.csv'

# Example of deprecating an exchange asset
- name: Deprecate Exchange Asset
  ap_exchange_asset:
    name: 'My Asset'
    state: 'deprecated'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    type: 'custom'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'

# Example of deleting an exchange asset
- name: Delete Exchange Asset
  ap_exchange_asset:
    name: 'home'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    type: 'custom'
    group_id: 'ee819df3-92cf-407a-adcd-098ff64131f1'
    asset_id: 'my-fragment'
    asset_version: '1.0.1'
'''

RETURN = '''
msg:
    description: Anypoint CLI command output
    type: str
    returned: always
'''

import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


def get_asset_identifier(group_id, asset_id, asset_version):
    return group_id + '/' + asset_id + '/' + asset_version


def execute_anypoint_cli(module, cmd):
    result = module.run_command(cmd)
    if result[0] != 0:
        module.fail_json(msg=result[1])

    return result[1]


def get_exchange_url(module):
    url = 'https://' + module.params['host'] + '/exchange/api/v2/assets/'
    url += get_asset_identifier(module.params['group_id'], module.params['asset_id'], module.params['asset_version'])
    return url


def execute_http_call(module, url, method, headers, payload):
    return_value = None
    try:
        if (headers is not None):
            if (payload is not None):
                return_value = open_url(url, method=method, headers=headers, data=payload)
            else:
                return_value = open_url(url, method=method, headers=headers)

    except Exception as e:
        module.fail_json(msg=str(e))

    return return_value


def analyze_asset(module):
    return_value = dict(
        must_update=False,
        deprecated=False
    )
    my_url = get_exchange_url(module)
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    output = execute_http_call(module, my_url, 'GET', headers, None)
    resp_json = json.loads(output.read())

    if (resp_json['status'] == 'deprecated'):
        return_value['deprecated'] = True

    # for now, only the tag list can change
    if (module.params['tags'] != resp_json['labels']):
        return_value['must_update'] = True

    return return_value


def look_asset_on_exchange(module):
    return_value = None
    # Query exchange using the Graph API
    my_url = 'https://' + module.params['host'] + '/graph/api/v1/graphql'
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = {
        'query': '{assets(query: {organizationIds: ["' + module.params['organization_id'] + '"],'
                 'searchTerm: "' + module.params['asset_id'] + '"'
                 ', offset: 0, limit: 100}){assetId groupId version type}}'
    }

    output = json.load(execute_http_call(module, my_url, 'POST', headers, json.dumps(payload)))

    # check if the environment exists
    for item in output['data']['assets']:
        if (module.params['asset_id'] == item['assetId']
                and module.params['group_id'] == item['groupId']
                and module.params['asset_version'] == item['version']
                and module.params['type'] == item['type']):
            return_value = item['assetId']

    return return_value


def get_context(module, cmd_base):
    return_value = dict(
        do_nothing=False,
        exists=False,
        must_update=False,
        deprecated=False
    )

    asset_id = look_asset_on_exchange(module)
    if (asset_id is not None):
        return_value['exists'] = True

    if (module.params['state'] == "present") or (module.params['state'] == "deprecated"):
        if (return_value['exists'] is True):
            result = analyze_asset(module)
            return_value['must_update'] = result['must_update']
            return_value['deprecated'] = result['deprecated']
            if (module.params['state'] == "present"):
                return_value['do_nothing'] = (return_value['must_update'] is False and return_value['deprecated'] is False)
            elif (module.params['state'] == "deprecated"):
                return_value['do_nothing'] = (return_value['deprecated'] is True)
    elif (module.params['state'] == "absent"):
        return_value['do_nothing'] = not return_value['exists']

    return return_value


def modify_exchange_asset(module, cmd_base, asset_identifier):
    modify_cmd = cmd_base
    modify_cmd += ' modify --tags "' + ','.join(module.params['tags']) + '"'
    modify_cmd += ' "' + asset_identifier + '"'
    execute_anypoint_cli(module, modify_cmd)

    return "Asset modified"


def upload_exchange_asset(module, cmd_base, asset_identifier):
    return_value = 'Asset uploaded'
    upload_cmd = cmd_base
    upload_cmd += ' upload'
    upload_cmd += ' --name "' + module.params['name'] + '"'
    if (module.params['main_file'] is not None):
        upload_cmd += ' --mainFile "' + module.params['main_file'] + '"'
    upload_cmd += ' --classifier "' + module.params['type'] + '"'
    upload_cmd += ' "' + asset_identifier + '"'
    if (module.params['file_path'] is not None):
        upload_cmd += ' "' + module.params['file_path'] + '"'
    execute_anypoint_cli(module, upload_cmd)
    if (module.params['tags']):
        modify_exchange_asset(module, cmd_base, asset_identifier)

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "deprecated", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        organization_id=dict(type='str', required=True),
        type=dict(type='str', required=True, choices=['custom', 'oas', 'wsdl']),
        group_id=dict(type='str', required=True),
        asset_id=dict(type='str', required=True),
        asset_version=dict(type='str', required=False, default="1.0.0"),
        api_version=dict(type='str', required=False, default="1.0"),
        main_file=dict(type='path', required=False, default=None),
        file_path=dict(type='path', required=False, default=None),
        tags=dict(type='list', required=False, default=[])
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

    if module.check_mode:
        module.exit_json(**result)

    cmd_base = get_anypointcli_path(module) + ' --bearer="' + module.params['bearer'] + '"'
    cmd_base += ' --host="' + module.params['host'] + '"'
    cmd_base += ' --organization="' + module.params['organization'] + '"'
    cmd_base += ' exchange asset'

    # convert empty strings to None if it is necessary
    if (module.params['main_file'] == ''):
        module.params['main_file'] = None
    if (module.params['file_path'] == ''):
        module.params['file_path'] = None
    # exit if I need to do nothing, so check if environment exists
    context = get_context(module, cmd_base)
    if (context['do_nothing'] is True):
        module.exit_json(**result)

    asset_identifier = get_asset_identifier(module.params['group_id'], module.params['asset_id'], module.params['asset_version'])
    if (module.params['state'] == 'present'):
        # if it doesn't exists then upload
        if (context['exists'] is False):
            output = upload_exchange_asset(module, cmd_base, asset_identifier)
        else:
            # if it exists and it is deprecated, then undeprecate it
            if (context['deprecated'] is True):
                undeprecate_cmd = cmd_base
                undeprecate_cmd += ' undeprecate "' + asset_identifier + '"'
                output = execute_anypoint_cli(module, undeprecate_cmd)
            # if it exists and must change then modify
            if (context['must_update'] is True):
                output = modify_exchange_asset(module, cmd_base, asset_identifier)
    elif (module.params['state'] == 'deprecated'):
        if (context['exists'] is False):
            output = upload_exchange_asset(module, cmd_base, asset_identifier)
        deprecate_cmd = cmd_base
        deprecate_cmd += ' deprecate "' + asset_identifier + '"'
        output = execute_anypoint_cli(module, deprecate_cmd)
    elif (module.params['state'] == 'absent'):
        delete_cmd = cmd_base
        delete_cmd += ' delete "' + asset_identifier + '"'
        output = execute_anypoint_cli(module, delete_cmd)

    result['msg'] = output.replace('\n', '')
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
