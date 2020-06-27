#! /usr/bin/env python2
# -*- coding: utf-8 -*-
""" Para controlar la carga del coche en función de la batería que existe en 
	el sistema FV y también dependiendo del botón que haya sido apretado en 
	el SonOff Dual del garaje.
	Primer botón: Carga solamente de la FV dependiendo de un SOC mínimo
	Segundo botón: Carga de la FV y si no ha acabado, conmuta a la red 
	después de las 23 horas (pendiente de implementar)
	Almacenamos en Mem2 la consigna de SOC Mínimo y en Mem3 si cargar o no de red
"""

import time, os, datetime, sys, json, logging
import config
import paho.mqtt.client as mqtt

# Definimos una constante con las cadenas para preguntar por MQTT de manera que el códgio sea más legible
Preguntas = {
    "Bateria": "R/{}/system/0/Dc/Battery/Soc".format(claves.VictronInterna),
    "SOCMinimo": "cmnd/CargaCoche/Mem2",
    "Reles": "cmnd/CargaCoche/STATUS",
    "CargadeRed": "cmnd/CargaCoche/Mem3",
    "Consumo": "R/{}/system/0/Ac/Consumption/L1/Power".format(claves.VictronInterna)
}


class AccesoMQTT:
    """ Para acceder al Venus GX a través de MQTT de cara a gestionar la recarga del coche del sistema FV
    """

    def __init__(self, debug=False):
        self.debug = debug
        # Creo el cliente
        self.client = mqtt.Client("Coche")
        # Conecto al broker
        self.client.connect(config.Venus)
        # Asigno la función que va a procesar los mensajes recibidos
        self.client.message_callback_add(
            'N{}'.format(Preguntas["Bateria"][1:]), self.lee_Bateria
        )
        self.client.message_callback_add(
            'N{}'.format(Preguntas["Consumo"][1:]), self.lee_Consumo
        )
        self.client.message_callback_add("stat/CargaCoche/STATUS", self.lee_EstadoDual)
        self.client.message_callback_add("stat/CargaCoche/RESULT", self.lee_Result)
        # Me subscribo a los tópicos necesarios, el SOC de la batería, el consumo y el estado del SonOff
        self.client.subscribe(
            [
                ('N{}'.format(Preguntas["Bateria"][1:]), 0),
                ('N{}'.format(Preguntas["Consumo"][1:]), 0),
                ("stat/CargaCoche/#", 0),
            ]
        )
        # Comenzamos el bucle
        self.client.loop_start()
        # Inicializamos la variable que servirá para que no me mande más de un mensaje a la hora
        self.bateria = 0
        self.hora = 0
        self.rele1 = 0
        self.rele2 = 0
        self.SOCMinimo = 50
        self.CargaRed = False
        self.consumo = 0
        # Obtenemos valores
        for f in Preguntas:
            self.pregunta(f)

    def lee_Bateria(self, client, userdata, message):
        """ Esta función es llamada para leer el estado de la batería
		"""
        # Lo importamos en formato json
        if self.debug:
            print(message.payload)
        # A veces recibimos mensajes vacíos, así que en ese caso ignoramos,
        # 	puesto que si no obtenemos un error en el json.loads()
        if len(message.payload.decode("utf-8")) == 0:
            return
        self.mensaje = json.loads(message.payload.decode("utf-8"))
        self.bateria = self.mensaje["value"]
        logging.debug("Bateria al {}%, {}".format(self.bateria, self.mensaje))
		# Cuando el coche está cargando, mostramos como va la batería
        if self.rele1:
            print("Bateria al {}%".format(self.bateria))

    def lee_Consumo(self, client, userdata, message):
        """ Esta función es llamada para leer el estado de la batería
		"""
        # Lo importamos en formato json
        if self.debug:
            print(message.payload)
        # A veces recibimos mensajes vacíos, así que en ese caso ignoramos,
        # 	puesto que si no obtenemos un error en el json.loads()
        if len(message.payload.decode("utf-8")) == 0:
            return
        self.mensaje = json.loads(message.payload.decode("utf-8"))
        self.consumo = self.mensaje["value"]
        logging.debug("Consumo: {}W, {}".format(round(self.consumo), self.mensaje))
		# Cuando el coche está cargando, mostramos como va la batería

    def lee_EstadoDual(self, client, userdata, message):
        """ Esta función es llamada para leer el estado de los Relés
		"""
        # Lo importamos en formato json
        self.mensaje = json.loads(message.payload.decode("utf-8"))
        if self.mensaje["Status"]["Power"] == 1 or self.mensaje["Status"]["Power"] == 3:
            self.rele1 = True
        else:
            self.rele1 = False
        if self.mensaje["Status"]["Power"] == 2 or self.mensaje["Status"]["Power"] == 3:
            self.rele2 = True
        else:
            self.rele2 = False
        logging.debug("Relé1 = {}, Relé2 = {}, {}".format(self.rele1, self.rele2, self.mensaje))
        if self.debug:
            print("Relé1 = {}, Relé2 = {}, {}".format(self.rele1, self.rele2, self.mensaje))
        # Lo mandamos a un fichero en el tmp para que podamos ver el estado en el st
        with open('/tmp/Coche', 'w') as file:
            file.writelines(str(self.rele1) + str(self.rele2))

    def lee_Result(self, client, userdata, message):
        """ Esta función es llamada para leer el tanto el SOC Mínimo que tenemos que dejar en la batería
			como el estado de los relés cuando se activan o desactivan
		"""
        # Lo importamos en formato json
        self.mensaje = json.loads(message.payload.decode("utf-8"))
		# Asignamos la consigna de SOC Mínimo
        if "Mem2" in self.mensaje:
            self.SOCMinimo = int(self.mensaje["Mem2"])
        # Activamos la carga de red
        if "Mem3" in self.mensaje and int(self.mensaje["Mem3"]) == 1:
            self.CargaRed = True
        if "POWER1" in self.mensaje:
            if self.mensaje["POWER1"] == "ON":
                self.rele1 = True
            else:
                self.rele1 = False
        if "POWER2" in self.mensaje:
            if self.mensaje["POWER2"] == "ON":
                self.rele2 = True
            else:
                self.rele2 = False
        if self.debug:
            print(
                "SOC Mínimo {}%, Relé1 = {}, Relé2 = {}, {}".format(self.SOCMinimo, self.rele1, self.rele2, self.mensaje)
            )
        # Mostramos el estado del SonOff. Si ponemos el SOCMinimo a 10 continuará cargando indefinidamente
        logging.info(
            "SOC Mínimo {}%, Relé1 = {}, Relé2 = {}, {}".format(self.SOCMinimo, self.rele1, self.rele2, self.mensaje)
        )
        # Lo mandamos a un fichero en el tmp para que podamos ver el estado en el st
        with open('/tmp/Coche', 'w') as file:
            file.writelines(str(self.rele1) + str(self.rele2))

    def pregunta(self, que="Bateria"):
        """ Manda la petición por MQTT, por defecto, del estado de la batería
		"""
        # Pedimos por MQTT lo solicitado
        self.client.publish(Preguntas[que], "")
        time.sleep(0.5)

    def enciende(self, que=True):
        """ Manda la orden de activar el contactor de la FV o de la red, asegurándose de desconectar primero el 
        otro por si estuviera conectado para que no estén ambos a la vez.
        Por defecto, True, equivale al de la FV, que está conectado al relé 1
        """
        if que:
            mensaje = "Power2 OFF;DELAY 10;Power1 ON"
        else:
            mensaje = "Power1 OFF;DELAY 10;Power2 ON"
        # Mandamos la orden
        self.client.publish("cmnd/CargaCoche/backlog", mensaje)

    def controla(self):
        """ Controla el estado de la batería y del relé y activa o desactiva 
			en función de la hora y el % de SOC
		"""
        # Obtenemos los datos de estado de la batería y consumo
        self.pregunta()
        self.pregunta("Consumo")
        # Nos quedamos con la hora para no saturar de mensajes en la misma hora
        hora = datetime.datetime.now().hour
        mensaje = ""
		# Si está activo el relé de la FV, es decir, estamos supuestamente cargando el coche, 
		# pero el consumo no lo refleja, desconectamos el relé y desactivamos la carga subiendo la consigna
        if self.rele1 and self.consumo < 2000:
            self.client.publish("cmnd/CargaCoche/POWER1", "Off")
            self.client.publish("cmnd/CargaCoche/Mem2", "100")
            logging.info('No hay consumo, por lo que el coche ya está cargado o no conectado. Desconectamos')
            os.system(
                'echo Desconectamos el relé por falta de consumo |mutt -s "No hay consumo {} y batería al {}% {}'.format(self.consumo, self.bateria, config.Email)
            )
            return
        # Si está activo el relé, la batería está por debajo del 50% y son entre las 8 y las 20
        if self.rele1 and self.bateria <= self.SOCMinimo and hora > 8 and hora < 20:
            # Deberíamos de cortar la carga o pasar a la red, dependiendo de
            # 	lo que hayamos pedido
            # Esto lo controlaremos más adelante usando los dos botones que
            # 	nos ofrece el SonOff Dual para ponerlos externos, seguramente
            # 	en la carcasa del cuadro. Por ahora, solo cargamos de la FV
            self.client.publish("cmnd/CargaCoche/POWER1", "OFF")
            logging.info("Desconectamos el coche al {}%".format(self.bateria))
            # Enviamos un mail comunicando el apagado si no lo hemos enviado antes
            if not hora == self.hora:
                os.system(
                    'echo Desconectamos el coche |mutt -s "La batería está al {}%" {}'.format(self.bateria, config.Email)
                )
                self.hora = hora
                mensaje = "y mandamos correo"
            logging.info("Batería al {}%, desconectamos {}".format(self.bateria, mensaje))
        # Si no está activo el relé y tenemos más del SOC Mínimo + un 15% adicional de batería,
        if (
            not self.rele1
            and self.bateria > self.SOCMinimo + 15
            and hora > 8
            and hora < 20
        ):
            # Volvemos a conectarlo
            self.enciende()
            if not hora == self.hora:
                os.system(
                    'echo Conectamos el coche |mutt -s "La batería está al {}%" {}'.format(self.bateria, config.Email)
                )
                self.hora = hora
                mensaje = "y mandamos correo"
            logging.info("Batería al {}%, conectamos {}".format(self.bateria, mensaje))
        # Si estamos cargando, mostramos el consumo
        if self.rele1:
            print("Consumo: {}W".format(self.consumo))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        debug = True
        nivel = logging.DEBUG
    else:
        debug = False
        nivel = logging.INFO
    # Inicializamos el logging
    logging.basicConfig(
        handlers=[logging.FileHandler("/tmp/Bateria.log"), logging.StreamHandler()],
        format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        level=nivel,
    )
    # Inicializamos el objeto para acceder al MQTT
    victron = AccesoMQTT(debug)
    # Nos quedamos en bucle eterno controlando cada 2 minutos
    while True:
        victron.controla()
        time.sleep(120)
