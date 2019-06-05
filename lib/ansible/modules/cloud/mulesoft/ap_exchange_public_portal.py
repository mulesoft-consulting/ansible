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
module: ap_exchange_public_portal

short_description: Update Anypoint Platform Exchange Public portal

version_added: "2.8"

description:
    - "Update the whole content of the Anypoint Platform Exchange Public portal"

options:
    bearer:
        description:
            - Anypoint Platform access token for an active session
        required: true
    state:
        description:
            - Assert the state of the environment. Use C(default) to set default values and C(modified) to make changes it.
        required: true
        choices: [ "default", "modified" ]
    host:
        description:
            - The host of your Anypoint Platform Installation
        required: false
        default: anypoint.mulesoft.com
    home:
        description:
            - represents the home page of the Anypoint Exchange Public Portal
        suboptions:
            hero_image:
                description:
                    - path to the home hero image file
                required: false
            text_color:
                description:
                    - home text color
                required: false
            welcome_title:
                description:
                    - home welcome title
                required: false
            welcome_text:
                description:
                    - home welcome text
                required: false
    navbar:
        description:
            - represents the navigation bar of the Anypoint Exchange Public Portal
        suboptions:
            logo_image:
                description:
                    - path to the navbar logo image file
                required: false
            fav_icon:
                description:
                    - path to the navbar fave icon file
                required: false
            text_color:
                description:
                    - portal text color
                required: false
            text_color_active:
                description:
                    - portal text color
                required: false
            background_color:
                description:
                    - navbar background color
                required: false

author:
    - Gonzalo Camino (@gonzalo-camino)

requirements:
   - requests

'''

EXAMPLES = '''
# Update the portal setting also the heroImage and the logoImage
- name: update exchange public portal with no content
  ap_exchange_public_portal_page:
    state: 'modified'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
    home:
        hero_image: '/tmp/my_hero_image.png'
    navbar:
        logo_image: '/tmp/my_logo_image.png'

# Leave the portal with default settings
- name: update exchange public portal with no content
  ap_exchange_public_portal_page:
    state: 'absent'
    bearer: 'fe819df3-92cf-407a-adcd-098ff64131f0'
'''

RETURN = '''
message:
    description: The output message that the module generates
    type: string
    returned: always
'''

import json
import os
import traceback
LIB_IMP_ERR = None
try:
    import requests
    HAS_LIB = True
except:
    HAS_LIB = False
    LIB_IMP_ERR = traceback.format_exc()

from pprint import pprint
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def get_anypoint_base_url(module):
    return 'https://' + module.params['host']


def get_domain(module):
    server_name = get_anypoint_base_url(module)
    api_endpoint = '/accounts/api/profile'
    my_url = server_name + api_endpoint
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + module.params['bearer']}

    try:
        resp = open_url(my_url, method="GET", headers=headers)
    except Exception as e:
        module.fail_json(msg='[get_domain] ' + str(e))

    resp_json = json.loads(resp.read())
    return resp_json["organization"]["domain"]


def get_exchange_portal_base_url(module):
    return get_anypoint_base_url(module) + '/exchange/api/v1/organizations/' + get_domain(module) + '/portal'


def do_no_action(module):
    return False


def get_portal_draft_content(module, portal_url):
    my_url = portal_url + '/draft'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }
    try:
        resp = open_url(my_url, method="GET", headers=headers)
    except Exception as e:
        module.fail_json(msg='[get_portal_draft_content] ' + str(e))
    resp_json = json.loads(resp.read())

    return resp_json


def create_image_resource(module, portal_resources_url, file_name):
    image_filename = os.path.basename(file_name)
    data = {
        'data': (image_filename, open(file_name, 'rb'), 'image/png')
    }
    headers = {
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    try:
        r = requests.Request('POST', portal_resources_url, files=data, headers=headers)
        prepared = r.prepare()
        # pprint(dict(prepared.headers))
        # print prepared.body
        s = requests.Session()
        resp = s.send(prepared)
        resp_json = json.loads(resp.text)
    except Exception as e:
        module.fail_json(msg='[create_image_resource] ' + str(e))

    return resp_json["path"]


def get_exchange_portal_resources_url(module):
    return get_anypoint_base_url(module) + '/exchange/api/v2/portals/' + get_domain(module) + '/draft/resources'


def publish_portal(module, portal_url, set_default_content):
    my_url = portal_url + '/draft'

    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + module.params['bearer']
    }

    if (set_default_content is True):
        payload = {
            'draft': True,
            'pages': [],
            'customization': {
                'home': {},
                'login': {}
            }
        }
    else:
        payload = get_portal_draft_content(module, portal_url)

        # Set Home page values
        portal_resources_url = get_exchange_portal_resources_url(module)
        # Set Home Page values (only those present)
        if ('home' not in payload['customization'].keys()):
            payload['customization'].update({'home': {}})
        if (module.params['home']['hero_image'] is not None):
            created_resource_path = create_image_resource(module, portal_resources_url, module.params['home']['hero_image'])
            payload['customization']['home']['heroImage'] = created_resource_path
        if (module.params['home']['text_color'] is not None):
            payload['customization']['home']['textColor'] = module.params['home']['text_color']
        if (module.params['home']['welcome_title'] is not None):
            payload['customization']['home']['welcomeTitle'] = module.params['home']['welcome_title']
        if (module.params['home']['welcome_text'] is not None):
            payload['customization']['home']['welcomeText'] = module.params['home']['welcome_text']

        # Set NavBar values (only those present)
        if ('navbar' not in payload['customization'].keys()):
            payload['customization'].update({'navbar': {}})
        if (module.params['navbar']['logo_image'] is not None):
            created_resource_path = create_image_resource(module, portal_resources_url, module.params['navbar']['logo_image'])
            payload['customization']['navbar']['logoImage'] = created_resource_path
        if (module.params['navbar']['fav_icon'] is not None):
            created_resource_path = create_image_resource(module, portal_resources_url, module.params['navbar']['fav_icon'])
            payload['customization']['navbar']['favicon'] = created_resource_path
        if (module.params['navbar']['text_color'] is not None):
            payload['customization']['navbar']['textColor'] = module.params['navbar']['text_color']
        if (module.params['navbar']['text_color_active'] is not None):
            payload['customization']['navbar']['textColorActive'] = module.params['navbar']['text_color_active']
        if (module.params['navbar']['background_color'] is not None):
            payload['customization']['navbar']['backgroundColor'] = module.params['navbar']['background_color']

    # update content
    try:
        resp = open_url(my_url, method="PUT", headers=headers, data=json.dumps(payload))
    except Exception as e:
        module.fail_json(msg='[publish_portal:1] ' + str(e))
    # publish
    my_url = portal_url
    try:
        resp = open_url(my_url, method="PATCH", headers=headers)
    except Exception as e:
        module.fail_json(msg='[publish_portal:2] ' + str(e))


def update_page(module, set_default_content):
    exchange_portal_base_url = get_exchange_portal_base_url(module)
    publish_portal(module, exchange_portal_base_url, set_default_content)


def run_module():
    # define suboptions specs
    default_values = dict(
        home_text_color='#FFFFFF',
        home_welcome_title='Welcome to your developer portal!',
        home_welcome_text='Build your application network faster! Get started with powerful tools, ' +
                          'intuitive interface, and best in class documentation experience.',
        navbar_text_color='#FFFFFF',
        navbar_text_color_active='#00A2DF',
        navbar_background_color='#262728'
    )

    home_spec = dict(
        hero_image=dict(type='str', required=False),
        text_color=dict(type='str', required=False),
        welcome_title=dict(type='str', required=False),
        welcome_text=dict(type='str', required=False)
    )

    navbar_spec = dict(
        logo_image=dict(type='str', required=False),
        fav_icon=dict(type='str', required=False),
        text_color=dict(type='str', required=False),
        text_color_active=dict(type='str', required=False),
        background_color=dict(type='str', required=False)
    )

    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        bearer=dict(type='str', required=True),
        host=dict(type='str', required=False, default='anypoint.mulesoft.com'),
        state=dict(type='str', required=True, choices=["default", "modified"]),
        home=dict(type='dict', options=home_spec),
        navbar=dict(type='dict', options=navbar_spec)
    )

    result = dict(
        changed=False,
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # exit if I need to do nothing, so check if asset exists in exchange
    if do_no_action(module) is True:
        module.exit_json(**result)

    # Main Module Logic
    set_default_content = (module.params['state'] == 'default')

    # finally update the portal with either default values or with specified ones
    update_page(module, set_default_content)
    result['message'] = 'home page updated'
    result['changed'] = True
    module.exit_json(**result)


def main():
    if not HAS_LIB:
        module.fail_json(msg=missing_required_lib("requests"),
                     exception=LIB_IMP_ERR)
    run_module()


if __name__ == '__main__':
    main()
