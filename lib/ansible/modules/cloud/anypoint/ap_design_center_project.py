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
        choices: [ "present", "published", "unpublished", "absent" ]
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
        choices: [ "trait", "resource-type", "library", "type", "user-documentation", "example" ]
        required: false
    project_dir:
        description:
            - Directory with project files. Optional for C(present) and C(published) states
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
                    - A list of tags for the asset
                type: list
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
            name:
                description:
                    - The assets name
                    - By default the same name of the Design Center project will be used
                required: false
            description:
                description:
                    - The assets description
                    - By default there is no description
                required: false
            icon:
                description:
                    - Path to the asset icon file.
                    - Supported extensions are svg, png, jpg, jpeg
                type: path
                required: false

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
    type: str
    returned: always
'''

import os
import shutil
import re
import json
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url
from ansible.module_utils.cloud.anypoint import ap_common
from ansible.module_utils.cloud.anypoint import ap_exchange_common


def get_context_design_center(module, cmd_base):
    return_value = None
    cmd_final = cmd_base + ' list --output json --pageIndex 0 --pageSize 500'
    cmd_final += ' "' + module.params['name'] + '"'

    result = ap_common.execute_anypoint_cli('[get_context_design_center]', module, cmd_final)

    # check if the project exists on design center
    if (result != '\n'):
        if (len(result) > 2):
            resp_json = json.loads(result)
            for item in resp_json:
                if (module.params['name'] == item['Name']):
                    return_value = item['ID']

    return return_value


def get_context_exchange(module):
    return_value = None
    asset_type = module.params['type']
    if (module.params['type'] == 'raml'):
        asset_type = 'rest-api'
    # Query exchange using the Graph API
    em = module.params.get('exchange_metadata')
    output = ap_exchange_common.look_exchange_asset_with_graphql(module, em.get('group_id'), em.get('asset_id'), em.get('asset_version'))
    # check if the environment exists
    if (output['data'] is not None):
        for item in output['data']['assets']:
            if (module.params['exchange_metadata']['asset_id'] == item['assetId']
                    and module.params['exchange_metadata']['group_id'] == item['groupId']
                    and module.params['exchange_metadata']['asset_version'] == item['version']
                    and asset_type == item['type']):
                return_value = item['assetId']

    return return_value


def get_context(module, cmd_base):
    return_value = dict(
        design_center_id=None,
        exchange_id=None,
        exchange_must_update=False,
        exchange_must_update_name=False,
        exchange_must_update_icon=False,
        exchange_must_update_description=False,
        exchange_must_update_tags=False

    )
    return_value['design_center_id'] = get_context_design_center(module, cmd_base)
    if (module.params['state'] == 'published' or module.params['state'] == 'unpublished'):
        return_value['exchange_id'] = get_context_exchange(module)
        if ((return_value['exchange_id'] is not None) and (module.params['state'] == 'published')):
            em = module.params.get('exchange_metadata')
            output = ap_exchange_common.analyze_asset(
                module, em.get('group_id'), em.get('asset_id'), em.get('asset_version'),
                em.get('name'), em.get('description'), em.get('icon'), em.get('tags'))
            return_value['exchange_must_update'] = output['must_update']
            return_value['exchange_must_update_name'] = output['must_update_name']
            return_value['exchange_must_update_icon'] = output['must_update_icon']
            return_value['exchange_must_update_description'] = output['must_update_description']
            return_value['exchange_must_update_tags'] = output['must_update_tags']
    return return_value


def get_uuid_regex():
    # return '[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}'
    return r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'


def get_org_id_regex():
    # using FOLDER_GROUP_ID for compatibility with some old
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
    regex = r'"groupId":\s?"' + get_org_id_regex() + r'"'
    new_string = r'"groupId": "' + org_id + r'"'
    replace_file_str_regex(exchange_file, regex, new_string)

    # replace org id in all .raml files ()
    # we could force to have only 1 file with a fixed name instead...
    for file in os.listdir(project_dir):
        if file.endswith(".raml"):
            raml_file = os.path.join(project_dir, file)
            regex = r'exchange_modules\/' + get_org_id_regex() + r'\/'
            new_string = 'exchange_modules/' + org_id + '/'
            replace_file_str_regex(raml_file, regex, new_string)


def create_empty_project(module, cmd_base):
    cmd_final = cmd_base + " create --type " + module.params['type']
    if (module.params['type'] == 'raml-fragment'):
        cmd_final += " --fragment-type " + module.params['fragment_type']
    cmd_final += ' "' + module.params['name'] + '"'
    result = ap_common.execute_anypoint_cli('[create_empty_project]', module, cmd_final)

    return result


def upload_project(module, cmd_base):
    cmd_final = cmd_base + ' upload'
    cmd_final += ' "' + module.params['name'] + '"'
    cmd_final += ' "' + module.params['project_dir'] + '"'

    result = ap_common.execute_anypoint_cli('[upload_project]', module, cmd_final)

    return result


def publish_project_to_exchange(module, context, cmd_base):
    cmd_final = cmd_base
    cmd_final += ' publish'

    # Parameters processing
    cmd_final += ' --main "' + module.params['exchange_metadata']['main'] + '"'
    cmd_final += ' --apiVersion "' + module.params['exchange_metadata']['api_version'] + '"'
    cmd_final += ' --groupId "' + module.params['exchange_metadata']['group_id'] + '"'
    cmd_final += ' --assetId "' + module.params['exchange_metadata']['asset_id'] + '"'
    cmd_final += ' --version "' + module.params['exchange_metadata']['asset_version'] + '"'

    if (module.params['exchange_metadata']['tags']):
        tag_list = ','.join(module.params['exchange_metadata']['tags'])
        cmd_final += ' --tags "' + tag_list + '"'

    cmd_final += ' "' + module.params['name'] + '"'
    ap_common.execute_anypoint_cli('[publish_project_to_exchange]', module, cmd_final)
    # update asset description and icon if it is required (tags are handled at publishing time)
    em = module.params['exchange_metadata']
    if (em.get('description') is not None and em.get('description') != ''):
        context['exchange_must_update_description'] = True
    if (em.get('icon') is not None):
        context['exchange_must_update_icon'] = True
    if (em.get('name') is not None and em.get('name') != module.params['name']):
        context['exchange_must_update_name'] = True
    ap_exchange_common.modify_exchange_asset(
        module, em['group_id'], em['asset_id'], em['asset_version'], context, em.get('name'), em.get('description'), em.get('icon'), []
    )

    return 'Project published to Exchange'


def unpublish_project_from_exchange(module):
    em = module.params.get('exchange_metadata')
    ap_exchange_common.delete_exchange_asset(module, em.get('group_id'), em.get('asset_id'), em.get('asset_version'))
    return 'Asset unpublished from Exchange'


def delete_project(module, cmd_base):
    cmd_final = cmd_base + ' delete' ' "' + module.params['name'] + '"'
    result = ap_common.execute_anypoint_cli('[delete_project]', module, cmd_final)

    return result


def run_module():
    # define list specs
    exchange_metadata_spec = dict(
        main=dict(type='str', required=False, default=None),
        api_version=dict(type='str', required=False, default="1.0"),
        tags=dict(type='list', required=False, default=[]),
        group_id=dict(type='str', required=False, default=None),
        asset_id=dict(type='str', required=False, default=None),
        asset_version=dict(type='str', required=False, default="1.0.0"),
        name=dict(type='str', required=False, default=None),
        description=dict(type='str', required=False, default=''),
        icon=dict(type='path', required=False, default=None)
    )
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "published", "unpublished", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        organization_id=dict(type='str', required=False),
        type=dict(type='str', required=False, default="raml", choices=["raml", "raml-fragment"]),
        fragment_type=dict(type='str', required=False, default="trait", choices=["trait", "resource-type", "library", "type", "user-documentation", "example"]),
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
    anypoint_cli = ap_common.get_anypointcli_path(module)
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
        if (module.params['exchange_metadata'].get('icon') == ''):
            module.params['exchange_metadata']['icon'] = None
        if (module.params['exchange_metadata'].get('name') == ''):
            module.params['exchange_metadata']['name'] = None

        if module.params['type'] == 'raml-fragment':
            if module.params['fragment_type'] is None:
                module.fail_json(msg="present and published states on raml fragment needs 'fragment_type' option")

        if (module.params['project_dir'] is not None) and (module.params['organization_id'] is None):
            module.fail_json(msg="present and published states needs 'organization_id' option")

        # this is only required for published/unpublished state
        if (module.params['state'] == "published" or module.params['state'] == "unpublished"):
            # validate exchange required arguments without default value
            if module.params['exchange_metadata']['main'] is None:
                module.fail_json(msg="published|unpublished state needs 'exchange_metadata.main' option")
            if module.params['exchange_metadata']['group_id'] is None:
                module.fail_json(msg="published|unpublished state needs 'exchange_metadata.group_id' option")
            if module.params['exchange_metadata']['asset_id'] is None:
                module.fail_json(msg="published|unpublished state needs 'exchange_metadata.asset_id' option")
    # no specific parameters for deletion needs to be checked

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if asset exists in exchange
    context = get_context(module, cmd_base)

    # finally execute some stuff based on the actual state
    if (module.params['state'] == "present") or (module.params['state'] == "published"):
        # validate if don't need to make changes
        if ((module.params['state'] == "published")
                and (context['design_center_id'] is not None)
                and (context['exchange_id'] is not None)
                and (context['exchange_must_update'] is False)):
            # asset already exists, it is published and it doesn't requires metadata updates
            module.exit_json(**result)  # do nothing

        if (module.params['state'] == "present") and (context['design_center_id'] is not None) and (module.params['project_dir'] is None):
            # asset already exists and I don't care about the content, I could assume an empty project
            module.exit_json(**result)  # do nothing

        # design center part
        if (context['design_center_id'] is None):
            output = create_empty_project(module, cmd_base)

        if (module.params['project_dir'] is not None):
            prepare_project_to_upload(module.params['project_dir'], module.params['organization_id'])
            output = upload_project(module, cmd_base)

        # exchange part
        if (module.params['state'] == "published"):
            if (context['exchange_id'] is None):
                output = publish_project_to_exchange(module, context, cmd_base)
            # update metadata if it is required
            if (context['exchange_must_update'] is True):
                em = module.params['exchange_metadata']
                output = ap_exchange_common.modify_exchange_asset(
                    module, em.get('group_id'), em.get('asset_id'), em.get('asset_version'),
                    context, em.get('name'), em.get('description'), em.get('icon'), em.get('tags'))
    elif (module.params['state'] == "unpublished"):
        if (context['exchange_id'] is None):
            module.exit_json(**result)  # do nothing
        else:
            output = unpublish_project_from_exchange(module)
    elif (module.params['state'] == "absent"):
        if (context['design_center_id'] is None):
            module.exit_json(**result)  # do nothing
        else:
            output = delete_project(module, cmd_base)

    result['msg'] = output.replace('\n', '')
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
