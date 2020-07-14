#! /usr/bin/env python2
# -*- coding: utf-8 -*-
""" Programa para lanzar la carga nocturna del coche de la red    
"""

import CargaCoche

if len(CargaCoche.sys.argv) == 2:
    debug = True
    nivel = CargaCoche.logging.DEBUG
else:
    debug = False
    nivel = CargaCoche.logging.INFO
# Inicializamos el logging
CargaCoche.logging.basicConfig(
    filename="/tmp/Carga.log",
    format="%(asctime)s %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    level=nivel,
)

# Inicializamos el objeto para acceder al MQTT
victron = CargaCoche.AccesoMQTT(debug)
#victron.pregunta('CargaRed')
# Nos aseguraos de que ha leído todos los parámetros dejando un tiempo
#CargaCoche.time.sleep(2)
# Si está activada la variable, lanzamos la carga
if victron.cargaRed:
    victron.CargaNocturna()
else:
    CargaCoche.logging.info('No hay programada carga Nocturna')
# Cerramos bucle
victron.client.loop_stop()
