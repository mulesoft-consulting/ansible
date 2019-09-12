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
module: ap_design_center_project

short_description: Manage Projects on Design Center

version_added: "2.8"

description:
    - "This module supports basic operations create, publish and delete on Anypoint Platform Design Center"

options:
    name:
        description:
            - Project name
        required: true
    state:
        description:
            - Assert the state of the environment. Use C(present) to create a project, C(published) to publish it to Exchange and C(absent) to delete it.
        required: true
        choices: [ "present", "published", "absent" ]
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
            - Anypoint Platform Organization Id to work on. Required for C(present) and C(published) states
        required: false
    type:
        description:
            - Project type. Required for C(present) and C(published) states
        default: raml
        choices: ["raml", "raml-fragment"]
        required: false
    fragment_type:
        description:
            - Fragment type. Required for C(present) and C(published) states if type is C(raml-fragment)
        default: trait
        choices: [ "trait", "resource-type", "library", "type", "user-documentation" ]
        required: false
    project_dir:
        description:
            - Directory with project files. Optional for C(present) and C(published) states if type is C(raml-fragment)
        required: false
    exchange_metadata:
        description:
            - Describes the attributes of the object in Exchange. Required for C(published) state
        suboptions:
            main:
                description:
                    - The name of the main file name
                required: false
            api_version:
                description:
                    - The API version if your project is an API specification project
                required: false
                default: 1.0
            tags:
                description:
                    - Comma separated list of tags.
                required: false
            group_id:
                description:
                    - The assets groupId
                required: false
            asset_id:
                description:
                    - The assets assetId
                required: false
            asset_version:
                description:
                    - The assets version
                required: false
                default: 1.0.0

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - anypoint-cli
'''

EXAMPLES = '''
# Create a fragment project on design center
- name: Create a fragment project on design center
  ap_design_center_project:
    name: 'My Fragment'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    type: 'raml-fragment'
    fragment_type: 'trait'
    project_dir: '/tmp/my-fragment'

# Create a fragment project on Design Center and publish it to Exchange
- name: Create a fragment project on Design Center and publish it to Exchange
  ap_design_center_project:
    name: 'My Fragment'
    state: 'published'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    organization_id: 'fe819df3-92cf-407a-adcd-098ff64131f1'
    type: 'raml-fragment'
    fragment_type: 'trait'
    project_dir: '/tmp/my-fragment'
    exchange_metadata:
      main: 'fragment.raml'
      group_id: 'fe819df3-92cf-407a-adcd-098ff64131f1'
      asset_id: 'my-fragment'

# Delete a fragment project from Design Center
- name: Delete a fragment project from Design Center
  ap_design_center_project:
    name: 'My Fragment'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    type: 'raml-fragment'
'''

RETURN = '''
msg:
    description: Anypoint CLI command output
    type: string
    returned: always
'''

import os
import shutil
import re
import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def get_anypointcli_path(module):
    return module.get_bin_path('anypoint-cli', True, ['/usr/local/bin'])


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


def do_no_action_design_center(module, cmd_base):
    return_value = None
    cmd_final = cmd_base + ' list --output json --pageIndex 0 --pageSize 500'
    cmd_final += ' "' + module.params['name'] + '"'

    result = module.run_command(cmd_final)

    if result[0] != 0:
        module.fail_json(msg=result[1])

    # check if the project exists on design center
    if len(result[1]) > 2:
        resp_json = json.loads(result[1])
        for item in resp_json:
            if (module.params['name'] == item['Name']):
                return_value = item['ID']

    return return_value


def do_no_action_exchange(module):
    return_value = None
    if (module.params['type'] == 'raml'):
        asset_type = 'rest-api'
    elif (module.params['type'] == 'raml-fragment'):
        asset_type = 'raml-fragment'
    # Query exchange using the Graph API
    my_url = 'https://' + module.params['host'] + '/graph/api/v1/graphql'
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    payload = {
        'query': '{assets(query: {organizationIds: ["' + module.params['organization_id'] + '"],'
                 'searchTerm: "' + module.params['exchange_metadata']['asset_id'] + '"'
                 ', offset: 0, limit: 100}){assetId groupId version type}}'
    }

    output = json.load(execute_http_call(module, my_url, 'POST', headers, json.dumps(payload)))

    # check if the environment exists
    for item in output['data']['assets']:
        if (module.params['exchange_metadata']['asset_id'] == item['assetId']
                and module.params['exchange_metadata']['group_id'] == item['groupId']
                and module.params['exchange_metadata']['asset_version'] == item['version']
                and asset_type == item['type']):
            return_value = item['assetId']

    return return_value


def do_no_action(module, cmd_base):
    return_value = dict(
        design_center_id=None,
        exchange_id=None
    )
    return_value['design_center_id'] = do_no_action_design_center(module, cmd_base)
    if (module.params['state'] == 'published'):
        return_value['exchange_id'] = do_no_action_exchange(module)

    return return_value


def get_uuid_regex():
    return '[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}'


def get_org_id_regex():
    return '(' + get_uuid_regex() + '|FOLDER_GROUP_ID)'


def replace_str_in_file(file_name, old_str, new_str):
    f = open(file_name, 'r')
    filedata = f.read()
    f.close()

    newdata = filedata.replace(old_str, new_str)

    f = open(file_name, 'w')
    f.write(newdata)
    f.close()


def replace_file_str_regex(file_name, regex, rep_str):
    f = open(file_name, 'r')
    filedata = f.read()
    f.close()

    newdata = re.sub(regex, rep_str, filedata)

    f = open(file_name, 'w')
    f.write(newdata)
    f.close()


def prepare_project_to_upload(project_dir, org_id):
    # delete exchange_modules directory
    shutil.rmtree(project_dir + '/exchange_modules', ignore_errors=True, onerror=None)
    # replace org id in exchange.json file
    exchange_file = os.path.join(project_dir, 'exchange.json')
    regex = '"groupId":\s?"' + get_org_id_regex() + '"'
    new_string = '"groupId": "' + org_id + '"'
    replace_file_str_regex(exchange_file, regex, new_string)

    # replace org id in all .raml files ()
    # we could force to have only 1 file with a fixed name instead...
    for file in os.listdir(project_dir):
        if file.endswith(".raml"):
            raml_file = os.path.join(project_dir, file)
            regex = '\/exchange_modules\/' + get_org_id_regex() + '\/'
            new_string = '/exchange_modules/' + org_id + '/'
            replace_file_str_regex(raml_file, regex, new_string)


def create_empty_project(module, cmd_base):
    cmd_final = cmd_base + " create --type " + module.params['type']
    if (module.params['type'] == 'raml-fragment'):
        cmd_final += " --fragment-type " + module.params['fragment_type']
    cmd_final += ' "' + module.params['name'] + '"'
    result = module.run_command(cmd_final)

    return result


def upload_project(module, cmd_base):
    cmd_final = cmd_base + ' upload'
    cmd_final += ' "' + module.params['name'] + '"'
    cmd_final += ' "' + module.params['project_dir'] + '"'

    result = module.run_command(cmd_final)

    return result


def publish_project_to_exchange(module, cmd_base):
    cmd_final = cmd_base
    cmd_final += ' publish'

    # Parameters processing
    cmd_final += ' --main "' + module.params['exchange_metadata']['main'] + '"'
    cmd_final += ' --apiVersion "' + module.params['exchange_metadata']['api_version'] + '"'
    cmd_final += ' --groupId "' + module.params['exchange_metadata']['group_id'] + '"'
    cmd_final += ' --assetId "' + module.params['exchange_metadata']['asset_id'] + '"'
    cmd_final += ' --version "' + module.params['exchange_metadata']['asset_version'] + '"'

    if module.params['exchange_metadata']['tags'] is not None:
        cmd_final += ' --tags "' + module.params['tags'] + '"'

    cmd_final += ' "' + module.params['name'] + '"'
    result = module.run_command(cmd_final)

    return result


def delete_project(module, cmd_base):
    cmd_final = cmd_base + ' delete' ' "' + module.params['name'] + '"'
    result = module.run_command(cmd_final)

    return result


def run_module():
    # define list specs
    exchange_metadata_spec = dict(
        main=dict(type='str', required=False, default=None),
        api_version=dict(type='str', required=False, default="1.0"),
        tags=dict(type='str', required=False),
        group_id=dict(type='str', required=False, default=None),
        asset_id=dict(type='str', required=False, default=None),
        asset_version=dict(type='str', required=False, default="1.0.0")
    )
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "published", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        organization_id=dict(type='str', required=False),
        type=dict(type='str', required=False, default="raml", choices=["raml", "raml-fragment"]),
        fragment_type=dict(type='str', required=False, default="trait", choices=["trait", "resource-type", "library", "type", "user-documentation"]),
        project_dir=dict(type='str', required=False),
        exchange_metadata=dict(type='dict', options=exchange_metadata_spec)
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
    anypoint_cli = get_anypointcli_path(module)
    if (anypoint_cli is None):
        module.fail_json(msg="anypoint-cli binary not present on host")

    cmd = anypoint_cli + " --bearer=\"" + module.params['bearer'] + "\""
    cmd += " --host=\"" + module.params['host'] + "\""
    cmd += " --organization=\"" + module.params['organization'] + "\""
    cmd += " designcenter project"
    cmd_base = cmd

    # check arguments & command setting
    if (module.params['state'] == "present") or (module.params['state'] == "published"):
        if module.params['type'] is None:
            module.fail_json(msg="present and published states needs 'type' option")

        if module.params['type'] == 'raml-fragment':
            if module.params['fragment_type'] is None:
                module.fail_json(msg="present and published states on raml fragment needs 'fragment_type' option")

        if (module.params['project_dir'] is not None) and (module.params['organization_id'] is None):
            module.fail_json(msg="present and published states needs 'organization_id' option")

        # this is only required for published state
        if module.params['state'] == "published":
            # validate exchange required arguments without default value
            if module.params['exchange_metadata']['main'] is None:
                module.fail_json(msg="published state needs 'exchange_metadata.main' option")
            if module.params['exchange_metadata']['group_id'] is None:
                module.fail_json(msg="published state needs 'exchange_metadata.group_id' option")
            if module.params['exchange_metadata']['asset_id'] is None:
                module.fail_json(msg="published state needs 'exchange_metadata.asset_id' option")
    # no specific parameters for deletion needs to be checked

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if asset exists in exchange
    context = do_no_action(module, cmd_base)

    # finally execute some stuff based on the actual state
    if (module.params['state'] == "present") or (module.params['state'] == "published"):
        # validate if don't need to make changes
        if (module.params['state'] == "published") and (context['design_center_id'] is not None) and (context['exchange_id'] is not None):
            # asset already exists and it is published
            module.exit_json(**result)  # do nothing

        if (module.params['state'] == "present") and (context['design_center_id'] is not None) and (module.params['project_dir'] is None):
            # asset already exists and I don't care about the content, I could assume an empty project
            module.exit_json(**result)  # do nothing

        # design center part
        if (context['design_center_id'] is None):
            output = create_empty_project(module, cmd_base)
            if output[0] != 0:
                module.fail_json(msg=output[1])

        if (module.params['project_dir'] is not None):
            prepare_project_to_upload(module.params['project_dir'], module.params['organization_id'])
            output = upload_project(module, cmd_base)
            if output[0] != 0:
                module.fail_json(msg=output[1])

        # exchange part
        if (module.params['state'] == "published"):
            if (context['exchange_id'] is None):
                output = publish_project_to_exchange(module, cmd_base)

    elif (module.params['state'] == "absent"):
        if (context['design_center_id'] is None):
            module.exit_json(**result)  # do nothing
        else:
            output = delete_project(module, cmd_base)

    if output[0] != 0:
        module.fail_json(msg=output[1])

    result['msg'] = output[1]
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
