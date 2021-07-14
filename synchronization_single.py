#This is the modified code for sumo-carla co-sim using traci

#!/usr/bin/env python

# Copyright (c) 2020 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB).
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.
"""
Script to integrate CARLA and SUMO simulations
"""

# ==================================================================================================
# -- imports ---------------------------------------------------------------------------------------
# ==================================================================================================

import argparse
import logging
import time
import math
import copy
import csv
import numpy
import socketserver
from threading import Thread
from _thread import *
import socket
# ==================================================================================================
# -- find carla module -----------------------------------------------------------------------------
# ==================================================================================================

import glob
import os
import sys
sys.path.append("/home/carla1/Desktop")
sys.path.append("/usr/share/sumo/tools")
sys.path.append("/home/carla1/UnrealEngine_4.24/Engine/Binaries/Linux/carla/Co-Simulation/Sumo")
import CDS
import traci
try:
    sys.path.append(
        glob.glob('../../PythonAPI/carla/dist/carla-*%d.%d-%s.egg' %
                  (sys.version_info.major, sys.version_info.minor,
                   'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

# ==================================================================================================
# -- find traci module -----------------------------------------------------------------------------
# ==================================================================================================

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

# ==================================================================================================
# -- sumo integration imports ----------------------------------------------------------------------
# ==================================================================================================

from sumo_integration.bridge_helper import BridgeHelper  # pylint: disable=wrong-import-position
from sumo_integration.carla_simulation import CarlaSimulation  # pylint: disable=wrong-import-position
from sumo_integration.constants import INVALID_ACTOR_ID  # pylint: disable=wrong-import-position
from sumo_integration.sumo_simulation import SumoSimulation  # pylint: disable=wrong-import-position

# ==================================================================================================
# -- synchronization_loop --------------------------------------------------------------------------
# ==================================================================================================
CV_message = {"carla0":{"advice_speed": 0, "time_difference": 0, "navigation": "none","veh_speed":0},"carla1":{"time_difference":0,"advice_speed":0,"navigation": "none","veh_speed":0},"carla2":{"time_difference":0,"advice_speed":0,"navigation": "none","veh_speed":0}}
adspeed = str(CV_message['carla0']['advice_speed'])
td = str(CV_message['carla0']['time_difference'])
na = CV_message['carla0']['navigation']

class SimulationSynchronization(object):
    """
    SimulationSynchronization class is responsible for the synchronization of sumo and carla
    simulations.
    """
    def __init__(self,
                 sumo_simulation,
                 carla_simulation,
                 tls_manager='none',
                 sync_vehicle_color=False,
                 sync_vehicle_lights=False):

        self.sumo = sumo_simulation
        self.carla = carla_simulation

        self.tls_manager = tls_manager
        self.sync_vehicle_color = sync_vehicle_color
        self.sync_vehicle_lights = sync_vehicle_lights

        if tls_manager == 'carla':
            self.sumo.switch_off_traffic_lights()
        elif tls_manager == 'sumo':
            self.carla.switch_off_traffic_lights()

        # Mapped actor ids.
        self.sumo2carla_ids = {}  # Contains only actors controlled by sumo.
        self.carla2sumo_ids = {}  # Contains only actors controlled by carla.

        BridgeHelper.blueprint_library = self.carla.world.get_blueprint_library()
        BridgeHelper.offset = self.sumo.get_net_offset()

        # Configuring carla simulation in sync mode.
        settings = self.carla.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = self.carla.step_length
        self.carla.world.apply_settings(settings)

    def tick(self):
        """
        Tick to simulation synchronization
        """
        # -----------------
        # sumo-->carla sync
        # -----------------
        self.sumo.tick()

        # Spawning new sumo actors in carla (i.e, not controlled by carla).
        sumo_spawned_actors = self.sumo.spawned_actors - set(self.carla2sumo_ids.values())
        for sumo_actor_id in sumo_spawned_actors:
            self.sumo.subscribe(sumo_actor_id)
            sumo_actor = self.sumo.get_actor(sumo_actor_id)

            carla_blueprint = BridgeHelper.get_carla_blueprint(sumo_actor, self.sync_vehicle_color)
            if carla_blueprint is not None:
                carla_transform = BridgeHelper.get_carla_transform(sumo_actor.transform,
                                                                   sumo_actor.extent)

                carla_actor_id = self.carla.spawn_actor(carla_blueprint, carla_transform)
                if carla_actor_id != INVALID_ACTOR_ID:
                    self.sumo2carla_ids[sumo_actor_id] = carla_actor_id
            else:
                self.sumo.unsubscribe(sumo_actor_id)

        # Destroying sumo arrived actors in carla.
        for sumo_actor_id in self.sumo.destroyed_actors:
            if sumo_actor_id in self.sumo2carla_ids:
                self.carla.destroy_actor(self.sumo2carla_ids.pop(sumo_actor_id))

        # Updating sumo actors in carla.
        for sumo_actor_id in self.sumo2carla_ids:
            carla_actor_id = self.sumo2carla_ids[sumo_actor_id]

            sumo_actor = self.sumo.get_actor(sumo_actor_id)
            carla_actor = self.carla.get_actor(carla_actor_id)

            carla_transform = BridgeHelper.get_carla_transform(sumo_actor.transform,
                                                               sumo_actor.extent)
            if self.sync_vehicle_lights:
                carla_lights = BridgeHelper.get_carla_lights_state(carla_actor.get_light_state(),
                                                                   sumo_actor.signals)
            else:
                carla_lights = None

            self.carla.synchronize_vehicle(carla_actor_id, carla_transform, carla_lights)

        # Updates traffic lights in carla based on sumo information.
        if self.tls_manager == 'sumo':
            common_landmarks = self.sumo.traffic_light_ids & self.carla.traffic_light_ids
            for landmark_id in common_landmarks:
                sumo_tl_state = self.sumo.get_traffic_light_state(landmark_id)
                carla_tl_state = BridgeHelper.get_carla_traffic_light_state(sumo_tl_state)
                self.carla.synchronize_traffic_light(landmark_id, carla_tl_state)

        # -----------------
        # carla-->sumo sync
        # -----------------
        self.carla.tick()

        # Spawning new carla actors (not controlled by sumo)
        carla_spawned_actors = self.carla.spawned_actors - set(self.sumo2carla_ids.values())
        for carla_actor_id in carla_spawned_actors:
            carla_actor = self.carla.get_actor(carla_actor_id)

            type_id = BridgeHelper.get_sumo_vtype(carla_actor)
            color = carla_actor.attributes.get('color', None) if self.sync_vehicle_color else None
            if type_id is not None:
                sumo_actor_id = self.sumo.spawn_actor(type_id, color)
                if sumo_actor_id != INVALID_ACTOR_ID:
                    self.carla2sumo_ids[carla_actor_id] = sumo_actor_id
                    self.sumo.subscribe(sumo_actor_id)

        # Destroying required carla actors in sumo.
        for carla_actor_id in self.carla.destroyed_actors:
            if carla_actor_id in self.carla2sumo_ids:
                self.sumo.destroy_actor(self.carla2sumo_ids.pop(carla_actor_id))

        # Updating carla actors in sumo.
        for carla_actor_id in self.carla2sumo_ids:
            sumo_actor_id = self.carla2sumo_ids[carla_actor_id]

            carla_actor = self.carla.get_actor(carla_actor_id)
            sumo_actor = self.sumo.get_actor(sumo_actor_id)

            sumo_transform = BridgeHelper.get_sumo_transform(carla_actor.get_transform(),
                                                             carla_actor.bounding_box.extent)
            if self.sync_vehicle_lights:
                carla_lights = self.carla.get_actor_light_state(carla_actor_id)
                if carla_lights is not None:
                    sumo_lights = BridgeHelper.get_sumo_lights_state(sumo_actor.signals,
                                                                     carla_lights)
                else:
                    sumo_lights = None
            else:
                sumo_lights = None

            self.sumo.synchronize_vehicle(sumo_actor_id, sumo_transform, sumo_lights)

        # Updates traffic lights in sumo based on carla information.
        if self.tls_manager == 'carla':
            common_landmarks = self.sumo.traffic_light_ids & self.carla.traffic_light_ids
            for landmark_id in common_landmarks:
                carla_tl_state = self.carla.get_traffic_light_state(landmark_id)
                sumo_tl_state = BridgeHelper.get_sumo_traffic_light_state(carla_tl_state)

                # Updates all the sumo links related to this landmark.
                self.sumo.synchronize_traffic_light(landmark_id, sumo_tl_state)

    def close(self):
        """
        Cleans synchronization.
        """
        # Configuring carla simulation in async mode.
        settings = self.carla.world.get_settings()
        settings.synchronous_mode = False
        settings.fixed_delta_seconds = None
        self.carla.world.apply_settings(settings)

        # Destroying synchronized actors.
        for carla_actor_id in self.sumo2carla_ids.values():
            self.carla.destroy_actor(carla_actor_id)

        for sumo_actor_id in self.carla2sumo_ids.values():
            self.sumo.destroy_actor(sumo_actor_id)

        # Closing sumo and carla client.
        self.carla.close()
        self.sumo.close()




    """
    Entry point for sumo-carla co-simulation.
    """
    # # sumo_simulation = SumoSimulation(args.sumo_cfg_file, args.step_length, args.sumo_host,
    # #                                  args.sumo_port, args.sumo_gui, args.client_order)
    # # carla_simulation = CarlaSimulation(args.carla_host, args.carla_port, args.step_length)
    #
    # sumo_simulation = SumoSimulation(args["sumo_cfg_file"], args["step_length"], args["sumo_host"],
    #                                 args["sumo_port"], args["sumo_gui"], args["client_order"])
    # carla_simulation = CarlaSimulation(args["carla_host"], args["carla_port"], args["step_length"])
    # #carla_simulation = CarlaSimulation("127.0.0.1",2000,1)
    #
    # # synchronization = SimulationSynchronization(sumo_simulation, carla_simulation, args.tls_manager,
    # #                                              args.sync_vehicle_color, args.sync_vehicle_lights)
    # synchronization = SimulationSynchronization(sumo_simulation, carla_simulation,args["tls_manager"],
    #                                             args["sync_vehicle_color"], args["sync_vehicle_lights"])

    # step=0
    # initial_speed = {}
    # HDV_lane_id = {}
    # route_carla={"carla0":["3_2","5_4","3_6","1_6","5_2","1_4"]*5,"carla1":["5_4","3_6","1_6","5_2","1_4","3_2"]*5,"carla2":["3_6","1_6","5_2","1_4","3_2","5_4"]*5}
    # route_count={"carla0":0,"carla1":0,"carla2":0}


    # try:
    #     while True:

def synchronization_loop(args):
    exp_type="HDV_CV"
    sumo_simulation = SumoSimulation(args["sumo_cfg_file"], args["step_length"],exp_type, args["sumo_host"],
                                     args["sumo_port"], args["sumo_gui"], args["client_order"])
    carla_simulation = CarlaSimulation(args["carla_host"], args["carla_port"], args["step_length"])
    synchronization = SimulationSynchronization(sumo_simulation, carla_simulation, args["tls_manager"],
                                                args["sync_vehicle_color"], args["sync_vehicle_lights"])
    step = 0
    initial_speed = {}
    HDV_lane_id = {}
    route_count = {"carla0": 0, "carla1": 0, "carla2": 0}
    navigation_count={"carla0": 0, "carla1": 0, "carla2": 0}

    carla_veh_info_last_step=0        
    route_carla = {"carla0": ["3_2", "5_4", "3_6", "1_6", "5_2", "1_4"] * 5,
                       "carla1": ["5_4", "3_6", "1_6", "5_2", "1_4", "3_2"] * 5,
                       "carla2": ["3_6", "1_6", "5_2", "1_4", "3_2", "5_4"] * 5}
    carla_navigation={"carla0":["go straight, right lane"]+["go straight, right lane, no overtake", "turn right", "go straight", "turn left", "go straight", "turn left", "go straight", "turn left first, and stop here", "go straight, right lane, no overtake", "go straight", "go straight", "U turn first, and stop here", "go straight, left lane, no overtake", "go straight", "go straight", "turn right", "go straight", "turn right", "go straight", "turn right first, and stop here", "go straight, no overtake", "turn right", "go straight", "U turn fisrt, and stop here", "go straight, left lane, no overtake", "turn left", "go straight", "U turn first, and stop here", "go straight, no overtake", "turn left", "go straight", "U turn first, and stop here"]*5+["experiment ended, thank you!"],"carla1":["go straight, right lane"]+["go straight, left lane, no overtake", "go straight", "go straight", "turn right", "go straight", "turn right", "go straight", "turn right first, and stop here", "go straight, no overtake", "turn right", "go straight", "U turn fisrt, and stop here", "go straight, left lane, no overtake", "turn left", "go straight", "U turn first, and stop here", "go straight, no overtake", "turn left", "go straight", "U turn first, and stop here","go straight, right lane, no overtake", "turn right", "go straight", "turn left", "go straight", "turn left", "go straight", "turn left first, and stop here","go straight, right lane, no overtake", "go straight", "go straight", "U turn first, and stop here"]*5+["experiment ended, thank you!"],"carla2":["go straight, right lane"]+["go straight, right lane, no overtake", "go straight", "go straight", "U turn first, and stop here", "go straight, left lane, no overtake", "go straight", "go straight", "turn right", "go straight", "turn right", "go straight", "turn right first, and stop here", "go straight, no overtake", "turn right", "go straight", "U turn fisrt, and stop here", "go straight, left lane, no overtake", "turn left", "go straight", "U turn first, and stop here", "go straight, no overtake", "turn left", "go straight", "U turn first, and stop here","go straight, right lane, no overtake", "turn right", "go straight", "turn left", "go straight", "turn left", "go straight", "turn left first, and stop here"]*5+["experiment ended, thank you!"]}
    travel_time_output,deceleration_output,speed_record={},{},{}
    
    try:
        while True:
            start = time.time()
            synchronization.tick()
            veh_info_dict=sumo_simulation.get_veh_info()["veh_info_dic"]
            carla_veh_info=sumo_simulation.get_veh_info()["carla_veh_info"]
            print(carla_veh_info)
            step+=1
            for veh in veh_info_dict.items():
                if initial_speed.__contains__(veh[0])==False:
                    initial_speed[str(veh[0])]=traci.vehicle.getSpeed(veh[0])
                else:
                    if initial_speed[str(veh[0])]<traci.vehicle.getSpeed(veh[0]):
                        initial_speed[str(veh[0])] = traci.vehicle.getSpeed(veh[0])
                    else:
                         pass

                if veh[1]["lane_id"]=="11.0.88_4":
                    HDV_lane_id[str(veh[0])]="3_1"
                elif veh[1]["lane_id"]=="11.0.88_3":
                    HDV_lane_id[str(veh[0])] = "3_2"
                elif veh[1]["lane_id"]=="-6.0.00_3":
                    HDV_lane_id[str(veh[0])]="1_1"
                elif veh[1]["lane_id"]=="15.0.00_4":
                    HDV_lane_id[str(veh[0])] = "5_1"
                elif veh[1]["lane_id"]=="15.0.00_3":
                    HDV_lane_id[str(veh[0])] = "5_2"
                else:
                    pass
            cp_span = CDS.calculate_arrival_time(veh_info_dict, initial_speed)["cp_span"]
            veh_info_dict = CDS.calculate_arrival_time(veh_info_dict, initial_speed)["veh_info"]
            carla_veh_info = CDS.get_carla_lane_distance(carla_veh_info)
            #print(carla_veh_info)
            #global carla_veh_info_last_step
            if step==1:
                for carla_veh in carla_veh_info.items():
                    carla_veh_info[str(carla_veh[0])]["in_junction"]=False
                    carla_veh_info[str(carla_veh[0])]["in_detector"]=False
                    carla_veh_info[str(carla_veh[0])]["route"]=route_carla[str(carla_veh[0])][0]
                    carla_veh_info[str(carla_veh[0])]["navigation"]=carla_navigation[str(carla_veh[0])][0]
            elif step>1:
                for carla_veh in carla_veh_info.items():
                    carla_veh_info[str(carla_veh[0])]["route"]=route_carla[str(carla_veh[0])][math.floor(route_count[str(carla_veh[0])])]
                    print(str(carla_veh[0])+" route: "+str(carla_veh_info[str(carla_veh[0])]["route"]))
                    pos=carla_veh[1]["position"]
                    angle=carla_veh[1]["angle"]
                    if pos[0]<168 and pos[0]>117 and pos[1]>180 and pos[1]<222:
                        #if type(carla_veh[1]["distance_to_junction"])!=type(carla_veh_info_last_step[str(carla_veh[0])]["distance_to_junction"]):
                            #route_count[str(carla_veh[0])]+=0.5
                        in_junction=True
                    else:
                        in_junction=False
                    carla_veh_info[str(carla_veh[0])]["in_junction"]=in_junction
                    if str(carla_veh[0]) not in carla_veh_info_last_step:
                          carla_veh_info_last_step[carla_veh[0]]={"in_junction":False,"in_detector":False}
                    if in_junction==carla_veh_info_last_step[carla_veh[0]]["in_junction"]:
                       pass
                    else:
                       route_count[str(carla_veh[0])]+=0.5

                    carla_veh_info[str(carla_veh[0])]["navigation"]=carla_navigation[str(carla_veh[0])][math.floor(navigation_count[str(carla_veh[0])])]
                    #print(str(carla_veh[0])+" navigation: "+str(carla_veh_info[str(carla_veh[0])]["navigation"]))
                    pos=carla_veh[1]["position"]
                    if (pos[0]<164 and pos[0]>143 and pos[1]>7 and pos[1]<10 and ((angle>0 and angle<135) or (angle>315 and angle<360))) or (pos[0]<185 and pos[0]>166 and pos[1]>140 and pos[1]<143 and ((angle>0 and angle<45) or (angle>270 and angle<360))) or (pos[0]<155 and pos[0]>140 and pos[1]>175 and pos[1]<178 and angle>90 and angle<225) or (pos[0]<173 and pos[0]>170 and pos[1]>202 and pos[1]<214 and angle>0 and angle<180) or (pos[0]<240 and pos[0]>237 and pos[1]>210 and pos[1]<222 and angle>180 and angle<360) or (pos[0]<335 and pos[0]>332 and pos[1]>202 and pos[1]<217 and angle>0 and angle<180) or (pos[0]<375 and pos[0]>372 and pos[1]>212 and pos[1]<225 and angle>180 and angle<360) or (pos[0]<420 and pos[0]>408 and pos[1]>235 and pos[1]<238 and ((angle>0 and angle<90) or (angle>270 and angle<360))) or (pos[0]<412 and pos[0]>397 and pos[1]>275 and pos[1]<278 and angle>90 and angle<270) or (pos[0]<400 and pos[0]>386 and pos[1]>405 and pos[1]<402 and ((angle>0 and angle<90) or (angle>270 and angle<360))) or (pos[0]<390 and pos[0]>375 and pos[1]>437 and pos[1]<440 and angle>90 and angle<270) or (pos[0]<367 and pos[0]>364 and pos[1]>453 and pos[1]<467 and angle>180 and angle<360) or (pos[0]<333 and pos[0]>330 and pos[1]>452 and pos[1]<468 and angle>0 and angle<180) or (pos[0]<330 and pos[0]>327 and pos[1]>462 and pos[1]<482 and angle>180 and angle<360) or (pos[0]<298 and pos[0]>295 and pos[1]>465 and pos[1]<481 and angle>0 and angle<180) or (pos[0]<252 and pos[0]>220 and pos[1]>465 and pos[1]<475 and angle>135 and angle<315) or (pos[0]<226 and pos[0]>192 and pos[1]>420 and pos[1]<423 and ((angle>0 and angle<135) or (angle>315 and angle<360))) or (pos[0]<110 and pos[0]>86 and pos[1]>255 and pos[1]<258 and angle>45 and angle<225) or (pos[0]<140 and pos[0]>119 and pos[1]>224 and pos[1]<227 and ((angle>0 and angle<45) or (angle>225 and angle<360))) or (pos[0]<162 and pos[0]>141 and pos[1]>37 and pos[1]<40 and angle>135 and angle<315):
                        in_detector=True
                    else:
                        in_detector=False
                    carla_veh_info[str(carla_veh[0])]["in_detector"]=in_detector
                    if in_detector==carla_veh_info_last_step[carla_veh[0]]["in_detector"]:
                       pass
                    else:
                       navigation_count[str(carla_veh[0])]+=0.5

            else:
                 pass
            global CV_message
            carla_veh_info_last_step = copy.copy(carla_veh_info)
            synchronization_loop_return = CDS.cds(cp_span, carla_veh_info, HDV_lane_id, veh_info_dict,travel_time_output,deceleration_output,speed_record)
            CV_message=synchronization_loop_return["CV_message"]
            speed_record=synchronization_loop_return["speed_record"]
            deceleration_output=synchronization_loop_return["deceleration_output"]
            travel_time_output=synchronization_loop_return["travel_time_output"]
            out_put={"speed_record":speed_record,"deceleration_output":deceleration_output,"travel_time_output":travel_time_output}
            for carla_veh in carla_veh_info_last_step.items():
                CV_message[carla_veh[0]]["navigation"]=carla_veh[1]["navigation"]
            print(CV_message)


            end = time.time()
            elapsed = end - start
            if elapsed < args["step_length"]:
                time.sleep(args["step_length"] - elapsed)

    except KeyboardInterrupt:
        logging.info('Cancelled by user.')
        time_output=time.strftime("%m%d_%H%M")
        #with open('/home/carla3/Desktop/sumo_output/script_output_'+str(time_output)+'.xml', 'wb') as myFile:
            #myWriter = csv.writer(myFile)
            #myWriter.writerow(speed_record)
            #myWriter.writerow(deceleration_output)
            #myWriter.writerow(travel_time_output)
        numpy.save('/home/carla1/Desktop/sumo_output/HDV_CV/script_output_'+str(time_output)+'.npy', out_put)
        #numpy.save('/home/carla3/Desktop/sumo_output/script_output_'+str(time_output)+'.npy', deceleration_output)
        #numpy.save('/home/carla3/Desktop/sumo_output/script_output_'+str(time_output)+'.npy', travel_time_output)
    
    finally:
        logging.info('Cleaning synchronization')
    
        synchronization.close()



def main():
    synchronization_loop({"sumo_cfg_file": "/home/carla1/Desktop/sumo_model/map.sumocfg",
                     "step_length": 0.02,
                     "sumo_host": None, "sumo_port": None, "sumo_gui": True, "client_order": 1,
                     "carla_host": "127.0.0.1",
                     "carla_port": 2000,
                     "tls_manager": "none", "sync_vehicle_color": False, "sync_vehicle_lights": False})


class MyServer(socketserver.BaseRequestHandler):
    def handle(self):
        conn = self.request
        address,port = self.client_address
        while True:
            print(address)
            adspeed = str(CV_message['carla0']['advice_speed'])
            td = str(CV_message['carla0']['time_difference'])
            na = CV_message['carla0']['navigation']
            cpeed = adspeed
            ctd = td
            cna = na
            time.sleep(0.2)
            conn.sendall(cpeed.encode('utf-8'))
            ack = conn.recv(1024)
            print(ack)
            conn.sendall(ctd.encode('utf-8'))
            ack2 = conn.recv(1024)
            print(ack2)
            conn.sendall(cna.encode('utf-8'))
            ack3 = conn.recv(1024)
            print(ack3)


               
if __name__ == '__main__':
    server = socketserver.ThreadingTCPServer(('127.0.0.1', 8888), MyServer)
    print("start")
    Thread(target = main).start()
    server.serve_forever()



