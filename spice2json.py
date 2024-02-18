#!/usr/bin/env python3

import sys
import json

port_id_map = {}
current_id = 2 # Starting ID

def get_netid(netname):
    global current_id
    if netname not in port_id_map:
        port_id_map[netname] = current_id
        current_id += 1
    return port_id_map[netname]

def clump_transmission_gates(json_input):
    for module_name, module in json_input["modules"].items():
        trios_to_clump = []
        for inverter_name, inverter_cell in module["cells"].items():
            if inverter_cell["type"] != "$not":
                continue
            for nfet_name, nfet_cell in module["cells"].items():
                if nfet_cell["type"] != "nfet":
                    continue
                for pfet_name, pfet_cell in module["cells"].items():
                    if pfet_cell["type"] != "pfet":
                        continue
                    # Check if nfet/pfet drains and sources are shared
                    if nfet_cell["connections"]["D"] == pfet_cell["connections"]["D"] and \
                       nfet_cell["connections"]["S"] == pfet_cell["connections"]["S"]:
                        if inverter_cell["connections"]["A"] == nfet_cell["connections"]["G"] and \
                           inverter_cell["connections"]["Y"] == pfet_cell["connections"]["G"]:
                            trios_to_clump.append((nfet_name, pfet_name, inverter_name))
                        elif inverter_cell["connections"]["A"] == pfet_cell["connections"]["G"] and \
                             inverter_cell["connections"]["Y"] == nfet_cell["connections"]["G"]:
                            trios_to_clump.append((nfet_name, pfet_name, inverter_name))
                    # Check if nfet/pfet drains and sources are opposite
                    elif nfet_cell["connections"]["D"] == pfet_cell["connections"]["S"] and \
                         nfet_cell["connections"]["S"] == pfet_cell["connections"]["D"]:
                        if inverter_cell["connections"]["A"] == nfet_cell["connections"]["G"] and \
                           inverter_cell["connections"]["Y"] == pfet_cell["connections"]["G"]:
                            trios_to_clump.append((nfet_name, pfet_name, inverter_name))
                        elif inverter_cell["connections"]["A"] == pfet_cell["connections"]["G"] and \
                             inverter_cell["connections"]["Y"] == nfet_cell["connections"]["G"]:
                            trios_to_clump.append((nfet_name, pfet_name, inverter_name))

        # Create a new transmission gate cell and remove the individual nfet, pfet, and inverter cells
        for nfet_name, pfet_name, inverter_name in trios_to_clump:
            tg_name = f"{nfet_name}_{pfet_name}"
            tg_connections = {
                "A": json_input["modules"][module_name]["cells"][nfet_name]["connections"]["S"],
                "B": json_input["modules"][module_name]["cells"][nfet_name]["connections"]["D"],
                "C": json_input["modules"][module_name]["cells"][nfet_name]["connections"]["G"],
                "Cn": json_input["modules"][module_name]["cells"][pfet_name]["connections"]["G"],
            }
            tg_attributes = {
                "nfet": nfet_name,
                "pfet": pfet_name,
                "$not": inverter_name
            }
            json_input["modules"][module_name]["cells"][tg_name] = {
                "type": "TG",
                "connections": tg_connections,
                "port_directions": {
                    "A": "input",
                    "B": "output",
                    "C": "input",
                    "Cn": "input"
                },
                "attributes": tg_attributes
            }
            # Remove the nfet, pfet, and inverter cells from the module
            del json_input["modules"][module_name]["cells"][nfet_name]
            del json_input["modules"][module_name]["cells"][pfet_name]



def clump_inverters(json_input, vdd="VPWR", gnd="VGND"):
    for module_name, module in json_input["modules"].items():
        inverters_to_clump = []
        for pfet_name, pfet_cell in module["cells"].items():
            if pfet_cell["type"] != "pfet" or get_netid(vdd) not in pfet_cell["connections"]["D"] + pfet_cell["connections"]["S"]:
                continue
            for nfet_name, nfet_cell in module["cells"].items():
                if nfet_cell["type"] != "nfet" or get_netid(gnd) not in nfet_cell["connections"]["D"] + nfet_cell["connections"]["S"]:
                    continue
                if pfet_cell["connections"]["G"] != nfet_cell["connections"]["G"]:
                    continue
                possible_ys = []
                if pfet_cell["connections"]["D"] != [get_netid(vdd)]:
                    possible_ys += pfet_cell["connections"]["D"]
                if pfet_cell["connections"]["S"] != [get_netid(vdd)]:
                    possible_ys += pfet_cell["connections"]["S"]
                if nfet_cell["connections"]["D"] != [get_netid(gnd)]:
                    possible_ys += nfet_cell["connections"]["D"]
                if nfet_cell["connections"]["S"] != [get_netid(gnd)]:
                    possible_ys += nfet_cell["connections"]["S"]

                if len(possible_ys) != 2 or possible_ys[0] != possible_ys[1]:
                    continue
                inverters_to_clump.append((pfet_name, nfet_name, possible_ys[0]))

        # Create a new inverter cell and remove the individual pfet and nfet cells
        for pfet_name, nfet_name, y in inverters_to_clump:
            inverter_name = f"{pfet_name}_{nfet_name}"
            inverter_connections = {
                "A": json_input["modules"][module_name]["cells"][pfet_name]["connections"]["G"],
                "Y": [y]
            }
            inverter_attributes = {
                "pfet": pfet_name,
                "nfet": nfet_name
            }
            json_input["modules"][module_name]["cells"][inverter_name] = {
                "type": "$not",
                "connections": inverter_connections,
                "port_directions": {
                    "A": "input",
                    "Y": "output"
                },
                "attributes": inverter_attributes
            }
            # Remove the pfet and nfet cells from the module
            del json_input["modules"][module_name]["cells"][pfet_name]
            del json_input["modules"][module_name]["cells"][nfet_name]

def clump_tristate_buffers(json_input, vdd="VPWR", gnd="VGND"):
    for module_name, module in json_input["modules"].items():
        buffers_to_clump = []
        for inverter_name, inverter_cell in module["cells"].items():
            if inverter_cell["type"] != "$not":
                continue
            # find pfet1
            for pfet1_name, pfet1_cell in module["cells"].items():
                if pfet1_cell["type"] != "pfet":
                    continue
                if pfet1_cell["connections"]["D"] == [get_netid(vdd)]:
                    pmid = pfet1_cell["connections"]["S"]
                elif pfet1_cell["connections"]["S"] == [get_netid(vdd)]:
                    pmid = pfet1_cell["connections"]["D"]
                else:
                    continue
                A = pfet1_cell["connections"]["G"]
                # find pfet2
                for pfet2_name, pfet2_cell in module["cells"].items():
                    if pfet2_cell["type"] != "pfet":
                        continue
                    # find y
                    if pfet2_cell["connections"]["D"] == pmid:
                        y = pfet2_cell["connections"]["S"]
                    elif pfet2_cell["connections"]["S"] == pmid:
                        y = pfet2_cell["connections"]["D"]
                    else:
                        continue
                    # find ENn and En
                    if pfet2_cell["connections"]["G"] == inverter_cell["connections"]["A"]:
                        ENn = inverter_cell["connections"]["A"]
                        En = inverter_cell["connections"]["Y"]
                    elif pfet2_cell["connections"]["G"] == inverter_cell["connections"]["Y"]:
                        ENn = inverter_cell["connections"]["Y"]
                        En = inverter_cell["connections"]["A"]
                    else:
                        continue
                    # find nfet1
                    for nfet1_name, nfet1_cell in module["cells"].items():
                        if nfet1_cell["type"] != "nfet":
                            continue
                        # check gate
                        if nfet1_cell["connections"]["G"] != En:
                            continue
                        # find nmid
                        if nfet1_cell["connections"]["D"] == y:
                            nmid = nfet1_cell["connections"]["S"]
                        elif nfet1_cell["connections"]["S"] == y:
                            nmid = nfet1_cell["connections"]["D"]
                        else:
                            continue
                        # find nfet2
                        for nfet2_name, nfet2_cell in module["cells"].items():
                            if nfet2_cell["type"] != "nfet":
                                continue
                            # check gate
                            if nfet2_cell["connections"]["G"] != A:
                                continue
                            # check ground
                            if nfet2_cell["connections"]["S"] == nmid and nfet2_cell["connections"]["D"] == [get_netid(gnd)]:
                                pass
                            elif nfet2_cell["connections"]["D"] == nmid and nfet2_cell["connections"]["S"] == [get_netid(gnd)]:
                                pass
                            else:
                                continue
                            # done
                            buffers_to_clump.append((pfet1_name, pfet2_name, nfet1_name, nfet2_name, inverter_name, y))

        # Create a new tristate buffer cell and remove the individual pfets, nfets, and inverter cells
        for pfet1_name, pfet2_name, nfet1_name, nfet2_name, inverter_name, y in buffers_to_clump:
            buffer_name = f"{pfet1_name}_{pfet2_name}_{nfet1_name}_{nfet2_name}"
            buffer_connections = {
                "A": json_input["modules"][module_name]["cells"][pfet1_name]["connections"]["G"],
                "ENn": json_input["modules"][module_name]["cells"][pfet2_name]["connections"]["G"],
                "En": json_input["modules"][module_name]["cells"][nfet1_name]["connections"]["G"],
                "Y": y
            }
            buffer_attributes = {
                "pfet1": pfet1_name,
                "pfet2": pfet2_name,
                "nfet1": nfet1_name,
                "nfet2": nfet2_name,
                "$not": inverter_name
            }
            json_input["modules"][module_name]["cells"][buffer_name] = {
                "type": "tristate_buffer",
                "connections": buffer_connections,
                "port_directions": {
                    "A": "input",
                    "ENn": "input",
                    "En": "input",
                    "Y": "output"
                },
                "attributes": buffer_attributes
            }
            # Remove the pfets, nfets, and inverter cells from the module
            del json_input["modules"][module_name]["cells"][pfet1_name]
            del json_input["modules"][module_name]["cells"][pfet2_name]
            del json_input["modules"][module_name]["cells"][nfet1_name]
            del json_input["modules"][module_name]["cells"][nfet2_name]

def remove_duals(json_input):
    for module_name, module in json_input["modules"].items():
        for cell_name, cell in module["cells"].items():
            # Check if the cell is a tristate buffer
            if cell["type"] == "tristate_buffer":
                # Remove the "ENn" port
                if "ENn" in cell["connections"]:
                    del cell["connections"]["ENn"]
            # Check if the cell is a transmission gate
            elif cell["type"] == "TG":
                # Remove the "Cn" port
                if "Cn" in cell["connections"]:
                    del cell["connections"]["Cn"]


def parse_spice_to_json(spice_file):
    modules = {}


    with open(spice_file, 'r') as f:
        lines = f.readlines()
        subckt_found = False
        for line in lines:
            if line.startswith('.subckt'):
                subckt_found = True
                subckt_info = line.strip().split()
                subckt_name = subckt_info[1]
                subckt_ports = subckt_info[2:]
                modules[subckt_name] = {
                    "ports": {},
                    "cells": {}
                }
                for subckt_port in subckt_ports:
                    modules[subckt_name]["ports"][subckt_port] = {
                        "direction": "inout",
                        "bits": [get_netid(subckt_port)]
                    }
            elif subckt_found and line.startswith('.ends'):
                subckt_found = False
            elif subckt_found and line.startswith('X'):
                cell_info = line.strip().split()
                cell_name = cell_info[0]
                subckt_type = None
                connections = {}
                port_directions = {}
                attributes = {}
                parameter_start = len(cell_info)
                for i in range(len(cell_info)):
                    try:
                        param_name, param_value = cell_info[i].split('=')
                        parameter_start = min(i, parameter_start)
                        attributes[param_name] = param_value
                    except ValueError:
                        pass
                ports = cell_info[1:parameter_start-1]
                subckt_type = cell_info[parameter_start-1]
                if "fet" in subckt_type:
                    if "pfet" in subckt_type:
                        subckt_type = "pfet"
                    if "nfet" in subckt_type:
                        subckt_type = "nfet"
                    for i, port in enumerate(ports):
                        if i > 4:
                            raise ValueError("Exceeded maximum number of connections")
                        fet_ports = ["S", "G", "D", "B"]
                        if i < 4:
                            connections[fet_ports[i]] = [get_netid(port)]
                    port_directions["S"] = "input"
                    port_directions["G"] = "input"
                    port_directions["D"] = "output"
                    # port_directions["B"] = "input"
                else:
                    for i, port in enumerate(ports):
                        if i >= 26:
                            raise ValueError("Exceeded maximum number of connections")
                        connections[chr(65 + i)] = [get_netid(port)]
                        port_directions[chr(65 + i)] = "input"
                modules[subckt_name]["cells"][cell_name] = {
                    "type": subckt_type,
                    "connections": connections,
                    "port_directions": port_directions,
                    "attributes": attributes
                }

    json_data = {
        "modules": modules
    }

    clump_inverters(json_data)
    clump_transmission_gates(json_data)
    clump_tristate_buffers(json_data)
    remove_duals(json_data)


    return json.dumps(json_data, indent=2)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <spice_file>")
        sys.exit(1)

    spice_file = sys.argv[1]
    json_data = parse_spice_to_json(spice_file)
    print(json_data)
