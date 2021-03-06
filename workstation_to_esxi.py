#!/usr/bin/env python
#
# Copyright (C) 2015 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
This script will convert the workstation build to an ESXI compatible build.
Mainly it's dropping all networking specific stuff
"""

import os
import sys
import tempfile
import subprocess
from xml.etree import ElementTree as ET


if len(sys.argv) != 3:
    print("Usage: source.ova dst.ova")
    sys.exit(1)


namespaces = [
    ('cim',  "http://schemas.dmtf.org/wbem/wscim/1/common"),
    ('ovf',  "http://schemas.dmtf.org/ovf/envelope/1"),
    ('rasd', "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData"),
    ('vmw',  "http://www.vmware.com/schema/ovf"),
    ('vssd', "http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData"),
    ('xsi',  "http://www.w3.org/2001/XMLSchema-instance")
]

for prefix, uri in namespaces:
    ET.register_namespace(prefix, uri)


with tempfile.TemporaryDirectory() as tmp_dir:
    print("Temporary directory: {}".format(tmp_dir))
    subprocess.call(["tar", "-xvf", sys.argv[1], "-C", tmp_dir])

    ovf_path = os.path.join(tmp_dir, 'GNS3 VM.ovf')
    print("=> Content of GNS3 VM.ovf")
    with open(ovf_path) as f:
        print(f.read())

    tree = ET.parse(ovf_path)
    root = tree.getroot()

    # Drop nat network
    network_section = root.find("{http://schemas.dmtf.org/ovf/envelope/1}NetworkSection")

    nat_found = False
    hostonly_found = False

    for node in network_section.findall("{http://schemas.dmtf.org/ovf/envelope/1}Network"):
        network_name = node.get("{http://schemas.dmtf.org/ovf/envelope/1}name").lower()
        if network_name == "nat":
            network_section.remove(node)
            nat_found = True
        elif network_name == "hostonly":
            hostonly_found = True

    # Sometimes export bug we raise an error instead of broken the file
    if not hostonly_found or not nat_found:
        print("ERROR: a network is missing in the original OVA")
        sys.exit(1)

    virtual_hardware = root.find("{http://schemas.dmtf.org/ovf/envelope/1}VirtualSystem/{http://schemas.dmtf.org/ovf/envelope/1}VirtualHardwareSection")
    nodes_to_remove = set()
    # Drop all extra config
    for child in root.iter('{http://www.vmware.com/schema/ovf}ExtraConfig'):
        print("Remove {}".format(child.attrib["{http://www.vmware.com/schema/ovf}key"]))
        nodes_to_remove.add(child)

    # Drop the second ethernet adapter
    for item in root.iter('{http://schemas.dmtf.org/ovf/envelope/1}Item'):
        connection = item.find('{http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData}Connection')
        if connection is not None and connection.text.lower() == "nat":
            print("Remove nat adapter")
            virtual_hardware.remove(item)

    for node in nodes_to_remove:
        virtual_hardware.remove(node)

    #Add product informations require by VMware ESXi 6.5
    virtual_system = root.find("{http://schemas.dmtf.org/ovf/envelope/1}VirtualSystem")
    product_section = ET.SubElement(virtual_system, '{http://schemas.dmtf.org/ovf/envelope/1}ProductSection')
    info = ET.SubElement(product_section, '{http://schemas.dmtf.org/ovf/envelope/1}Info')
    info.text = "This section describes the OVF package itself."
    product = ET.SubElement(product_section, '{http://schemas.dmtf.org/ovf/envelope/1}Product')
    product.text = "GNS3"

    #tree.write(os.path.join(tmp_dir, 'GNS3 VM.ovf'), default_namespace="http://schemas.dmtf.org/ovf/envelope/1")
    tree.write(ovf_path)
    subprocess.call(["ovftool",
                     "--overwrite",
                     "--skipManifestCheck",
                     os.path.join(tmp_dir, 'GNS3 VM.ovf'),
                     sys.argv[2]])

