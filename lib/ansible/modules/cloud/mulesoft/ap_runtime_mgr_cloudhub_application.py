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
module: ap_runtime_mgr_cloudhub_application

short_description: Manage Applications on Runtime Manager

version_added: "2.8"

description:
    - "This module supports basic operations create, publish and delete of applications on Anypoint Platform Runtime Manager"

options:
    name:
        description:
            - Application name
        required: true
    state:
        description:
            - Assert the state of the application. Use C(present) to create an application, C(started) to start it
              or C(undeployed) to stop it, and C(absent) to delete it.
        required: true
        choices: [ "present", "started", "undeployed", "absent" ]
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
    environment:
        description:
            - Environment on the Business Group to work on
        required: false
        default: Sandbox
    file:
        description:
            - Deployable file .jar for mule 4 app or .zip for mule 3 app
            - Required for C(present) state
        required: false
    runtime:
        description:
            - Specify the name and version of the runtime you want to deploy
            - Required for C(present) state
        required: false
    workers:
        description:
            - Number of workers
        required: false
        default: 1
    worker_size:
        description:
            - size of the workers in vCores
        required: false
        choices: [ "0.1", "0.2", "1", "2", "4", "8", "16" ]
        default: "0.1"
    region:
        description:
            - Name of the region to deploy to
        required: false
        choices: [ "us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "eu-west-1", "eu-central-1",
                   "eu-west-2", "ap-northeast-1", "ap-southeast-1", "ap-southeast-2", "sa-east-1" ]
        default: "us-east-1"
    persistent_queues:
        description:
            - Enable or disable persistent queues. Can take C(true) or C(false) values
        required: false
        default: false
    persistent_queues_encripted:
        description:
            - Enable or disable persistent queue encryption. Can take C(true) or C(false) values
        required: false
        default: false
    static_ips_enabled:
        description:
            - Enable or disable static IPs. Can take C(Enabled) or C(Disabled) values
        required: false
        choices: [ "Enabled", "Disabled" ]
        default: 'Disabled'
    object_store_v1:
        description:
            - Enable or disable Object Store V1. Can take C(true) or C(false) values
        required: false
        default: false
    auto_restart:
        description:
            - Automatically restart app when not responding. Can take C(true) or C(false) values
        required: false
        default: false
    properties:
        description:
            - A list of properties with the format C(name:value)
            - The property to be set must be passed enclosed in quotes and characters C(:) and C(=) must be escaped
        required: false
    properties_file:
        description:
            - Overwrite all properties with values from this file. The file format is 1 or more lines in C(name:value) format
            - Set the absolute path of the properties file in your local hard drive.

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - anypoint-cli
'''

EXAMPLES = '''
# Create a fragment project on design center
- name: Create a fragment project on design center
  ap_runtime_mgr_cloudhub_application:
    name: 'customer-sapi'
    state: 'present'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'
    file: '/tmp/customer-sapi.jar'
    runtime: '4.1.5'
    workers: '1'
    worker_size: '0.2'
    region: 'us-west-1'
    auto_start: true
    properties:
        - "db.user\\=oliver"
        - "db.pswd\\=queen"

# Stop an application from Runtime Manager
- name: Stop an application from Runtime Manager
  ap_runtime_mgr_cloudhub_application:
    name: 'customer-sapi'
    state: 'undeployed'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'

# Start an application from Runtime Manager
- name: Stop an application from Runtime Manager
  ap_runtime_mgr_cloudhub_application:
    name: 'customer-sapi'
    state: 'started'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'

# Delete an application from Runtime Manager
- name: Delete an application from Runtime Manager
  ap_runtime_mgr_cloudhub_application:
    name: 'customer-sapi'
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    organization: 'My Demos'
    environment: 'Sandbox'
'''

RETURN = '''
url:
    description: application url
    type: string
    returned: always
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


def execute_anypoint_cli(module, cmd):
    result = module.run_command(cmd)
    if result[0] != 0:
        module.fail_json(msg=result[1])

    return result[1]


def get_application(module, cmd_base):
    return_value = {}
    error_msg = 'Error: No application with domain ' + module.params['name'] + ' found.\n'

    cmd_final = cmd_base + ' describe-json '
    cmd_final += ' "' + module.params['name'] + '"'

    result = module.run_command(cmd_final)

    if (result[0] == 255 and result[1] == error_msg):
        return_value = {}
    elif (result[0] != 0):
        module.fail_json(msg='Unkown Error getting description for application [' + module.params['name'] + ']')
    else:
        return_value = json.loads(result[1])

    return return_value


def application_needs_update(module, cloudhub_app):
    return_value = False
    # - object store v1 is not compared due to lacking of information in the
    #   describe oepration on anypoint-cli
    # - file name is not compared
    if ((cloudhub_app.get('region') != module.params['region'])
            or (cloudhub_app.get('muleVersion')['version'] != module.params['runtime'])
            or (cloudhub_app.get('persistentQueues') != module.params['persistent_queues'])
            or (cloudhub_app.get('persistentQueuesEncrypted') != module.params['persistent_queues_encripted'])
            or (cloudhub_app.get('staticIPsEnabled') != module.params['static_ips_enabled'])
            or (cloudhub_app.get('monitoringAutoRestart') != module.params['auto_restart'])
            or (cloudhub_app.get('workers')['amount'] != module.params['workers'])
            or (str(cloudhub_app.get('workers')['type']['weight']) != module.params['worker_size'])):
        return_value = True

    return return_value


def get_context(module, cmd_base):
    return_value = dict(
        do_nothing=False,
        app_url=None,
        app_status=None,
        must_update=False
    )
    cloudhub_app = get_application(module, cmd_base)
    return_value['app_url'] = cloudhub_app.get('fullDomain')
    return_value['app_status'] = cloudhub_app.get('status')

    if (module.params['state'] == 'present'):
        if (return_value['app_url'] is not None):
            return_value['must_update'] = application_needs_update(module, cloudhub_app)
            if (return_value['must_update'] is False):
                return_value['do_nothing'] = True
    elif (module.params['state'] == 'started'):
        if (return_value['app_url'] is not None):
            if ((return_value['app_status'] == 'STARTED') or (return_value['app_status'] == 'DEPLOYING')):
                return_value['do_nothing'] = True
        else:
            module.fail_json(msg='Error: "started" state requires a present object')
    elif (module.params['state'] == 'undeployed'):
        if (return_value['app_url'] is not None):
            if (return_value['app_status'] == 'UNDEPLOYED'):
                return_value['do_nothing'] = True
        else:
            module.fail_json(msg='Error: "undeployed" state requires a present object')
    elif (module.params['state'] == 'absent'):
        if (return_value['app_url'] is None) or (return_value['app_status'] == 'DELETED'):
            return_value['do_nothing'] = True

    return return_value


def create_or_update_cloudhub_application(module, cmd_base, context):
    return_value = dict(
        app_url=None,
        app_status=None,
        msg='[create_or_update_cloudhub_application] NOT_IMPLEMENTED'
    )

    cmd_final = cmd_base
    if (context['must_update'] is False):
        # return_value = create_cloudhub_application(module, cmd_base, context)
        cmd_final += ' deploy'
    else:
        # return_value = update_cloudhub_application(module, cmd_base, context)
        cmd_final += ' modify'
    # add all options
    cmd_final += ' --runtime "' + module.params['runtime'] + '"'
    cmd_final += ' --workers "' + str(module.params['workers']) + '"'
    cmd_final += ' --workerSize "' + module.params['worker_size'] + '"'
    cmd_final += ' --region "' + module.params['region'] + '"'
    cmd_final += ' --persistentQueues "' + str(module.params['persistent_queues']) + '"'
    cmd_final += ' --persistentQueuesEncrypted "' + str(module.params['persistent_queues_encripted']) + '"'
    cmd_final += ' --staticIPsEnabled "' + str(module.params['static_ips_enabled']) + '"'
    cmd_final += ' --objectStoreV1 "' + str(module.params['object_store_v1']) + '"'
    cmd_final += ' --autoRestart "' + str(module.params['auto_restart']) + '"'
    # validate properties option: either property list or property file
    if (module.params['properties_file'] is not None):
        cmd_final += ' --propertiesFile "' + module.params['properties_file'] + '"'
    else:
        # add property list only if needed
        for prop in module.params['properties']:
            cmd_final += ' --property "' + prop + '"'
    # add application name and file path
    cmd_final += ' ' + module.params['name']
    cmd_final += ' ' + module.params['file']

    # execute anypoint-cli command and save the output
    output = execute_anypoint_cli(module, cmd_final)
    return_value['msg'] = 'applicationis being deployed'
    # retrieve the app descripcion
    cloudhub_app = get_application(module, cmd_base)
    return_value['app_url'] = cloudhub_app.get('fullDomain')
    return_value['app_status'] = cloudhub_app.get('status')

    return return_value


def start_cloudhub_application(module, cmd_base, context):
    return_value = dict(
        app_url=None,
        app_status=None,
        msg='NOT_IMPLEMENTED'
    )
    cmd_final = cmd_base + ' start "' + module.params['name'] + '"'
    output = execute_anypoint_cli(module, cmd_final)
    return_value['app_url'] = context['app_url']
    return_value['app_status'] = 'STARTED'
    return_value['msg'] = output.replace('\n', '')

    return return_value


def undeploy_cloudhub_application(module, cmd_base, context):
    return_value = dict(
        app_url=None,
        app_status=None,
        msg='NOT_IMPLEMENTED'
    )
    cmd_final = cmd_base + ' stop "' + module.params['name'] + '"'
    output = execute_anypoint_cli(module, cmd_final)
    return_value['app_url'] = context['app_url']
    return_value['app_status'] = 'UNDEPLOYED'
    return_value['msg'] = output.replace('\n', '')

    return return_value


def delete_cloudhub_application(module, cmd_base, context):
    return_value = dict(
        app_url=None,
        app_status=None,
        msg='NOT_IMPLEMENTED'
    )
    cmd_final = cmd_base + ' delete "' + module.params['name'] + '"'
    output = execute_anypoint_cli(module, cmd_final)
    return_value['msg'] = output.replace('\n', '')

    return return_value


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type='str', required=True),
        state=dict(type='str', required=True, choices=["present", "started", "undeployed", "absent"]),
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        organization=dict(type='str', required=True),
        environment=dict(type='str', required=False, default='Sandbox'),
        file=dict(type='str', required=False),
        runtime=dict(type='str', required=False),
        workers=dict(type='int', required=False, default=1),
        worker_size=dict(type='str', required=False, default="0.1", choices=["0.1", "0.2", "1", "2", "4", "8", "16"]),
        region=dict(type='str',
                    required=False,
                    default='us-east-1',
                    choices=["us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1", "eu-west-1", "eu-central-1",
                             "eu-west-2", "ap-northeast-1", "ap-southeast-1", "ap-southeast-2", "sa-east-1"]),
        persistent_queues=dict(type='bool', required=False, default=False),
        persistent_queues_encripted=dict(type='bool', required=False, default=False),
        static_ips_enabled=dict(type='bool', required=False, default=False),
        object_store_v1=dict(type='bool', required=False, default=False),
        auto_restart=dict(type='bool', required=False, default=False),
        properties=dict(type='list', required=False),
        properties_file=dict(type='str', required=False)
    )

    result = dict(
        changed=False,
        app_url=None,
        app_status=None,
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

    cmd = anypoint_cli + ' --bearer="' + module.params['bearer'] + '"'
    cmd += ' --host="' + module.params['host'] + '"'
    cmd += ' --organization="' + module.params['organization'] + '"'
    cmd += ' --environment="' + module.params['environment'] + '"'
    cmd += ' runtime-mgr cloudhub-application'
    cmd_base = cmd

    # check arguments & command setting
    if (module.params['state'] == "present"):
        if (module.params['file'] is None):
            module.fail_json(msg="present states needs 'file' option")
        elif (module.params['runtime'] is None):
            module.fail_json(msg="present states needs 'runtime' option")

    # no specific parameters for other states needs to be checked

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if asset exists in exchange
    context = get_context(module, cmd_base)
    result['app_url'] = context['app_url']
    result['app_status'] = context['app_status']

    if (context['do_nothing'] is True):
        module.exit_json(**result)

    output = None
    # finally execute some stuff based on the actual state
    if (module.params['state'] == "present"):
        output = create_or_update_cloudhub_application(module, cmd_base, context)
    elif (module.params['state'] == "started"):
        output = start_cloudhub_application(module, cmd_base, context)
    elif (module.params['state'] == "undeployed"):
        output = undeploy_cloudhub_application(module, cmd_base, context)
    elif (module.params['state'] == "absent"):
        output = delete_cloudhub_application(module, cmd_base, context)

    result['app_url'] = output['app_url']
    result['app_status'] = output['app_status']
    result['msg'] = output['msg']
    result['changed'] = True

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
