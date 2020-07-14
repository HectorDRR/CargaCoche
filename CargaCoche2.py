#! /usr/bin/env python2
# -*- coding: utf-8 -*-
""" Para controlar la carga del coche en función de la batería que existe en 
	el sistema FV y también dependiendo del botón que haya sido apretado en 
	el SonOff Dual del garaje.
	Primer botón: Carga solamente de la FV dependiendo de un SOC mínimo
	Segundo botón: Carga de la FV y si no ha acabado, conmuta a la red 
	después de las 23 horas (pendiente de implementar)
	Almacenamos en Mem1 si cargar o no, Mem2 la consigna de SOC Mínimo y en Mem3 tipo de carga:
        0 = Cargamos solo de FV
        1 = Nocturna de red
    Programación de botones. Poniendo el weblog a 4 nos cuenta lo siguiente:
    Botón normal: code 0404 enciende, 0405 apaga
    Botón 0: code 0401 enciende, 0400 apaga
    Botón 1: code 0402 enciende, 0403 apaga
    Todos los detecta como Button1 multi-press 1
    Configuramos una regla en el SonOff para que cambie el comportamiento de los botones y que reinicie las
    variables, carga de fotovoltaica Mem1 a 1 y carga de red Mem3 a 0 a las 8 AM:
    *** Parece ser que los botones en pines activan directamente los relés, aunque le programemos una rule.
        El button0 se corresponde realmente con el 2 en la programación, y el 1 con el uno. La diferencia
        es que el botón normal, que también es el uno, si que solo hace lo definido en la rule. A la espera
        de ver si podemos cablear directamente el botón normal, pasamos a programar en la rule la desconexión
        de los relés.
    ***
    rule1 on button1#state do backlog mem1 1;power1 off endon on button2#state do backlog mem3 1;power2 off endon on time#Minute=480 do backlog mem1 1; mem3 0 endon
    Para que no haya problemas con las actualizaciones de las imágenes, tenemos que instalar las librerías
    en nuestro home, para ello creamos una carpeta lib en /home/root y en ella instalamos el Paho-MQTT y
    definimos un .bashrc donde hacemos un 
    export PYTHONPATH=/home/root/lib/
    Y como por alguna extraña razón se empeña en arrancar en sh en vez de bash, creamos un .profile que
    arranca el bash.
    
"""

import time, os, datetime, sys, json, logging
import config
import paho.mqtt.client as mqtt

# Definimos una constante con las cadenas para preguntar por MQTT de manera que el códgio sea más legible
Preguntas = {
    "Bateria": "R/{}/system/0/Dc/Battery/Soc".format(config.VictronInterna),
    "Consumo": "R/{}/system/0/Ac/Consumption/L1/Power".format(config.VictronInterna),
    "Carga": "cmnd/CargaCoche/Mem1",
    "SOCMinimo": "cmnd/CargaCoche/Mem2",
    "CargaRed": "cmnd/CargaCoche/Mem3",
    "Reles": "cmnd/CargaCoche/STATUS"
}

   
class AccesoMQTT:
    """ Para acceder al Venus GX a través de MQTT de cara a gestionar la recarga del coche del sistema FV
    """

    def __init__(self, debug=False):
        self.debug = debug
        # Creo el cliente
        self.client = mqtt.Client("Coche")
        # Conecto al broker
        self.client.connect('localhost')
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
        self.carga = True
        self.rele1 = 0
        self.rele2 = 0
        self.SOCMinimo = 50
        self.cargaRed = False
        self.consumo = 0
        self.flag = False
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
			como el estado de los relés cuando se activan o desactivan o si cargar o no por la noche
		"""
        global tiempo, conectado
        # Lo importamos en formato json
        self.mensaje = json.loads(message.payload.decode("utf-8"))
        # Asignamos la carga
        if "Mem1" in self.mensaje:
            if self.mensaje["Mem1"] == "1":
                self.carga = True
                self.flag = False
            else:
                self.carga = False
		# Asignamos la consigna de SOC Mínimo
        if "Mem2" in self.mensaje:
            self.SOCMinimo = int(self.mensaje["Mem2"])
        # Asignamos la carga de red
        if "Mem3" in self.mensaje:
            if self.mensaje["Mem3"] == "1":
                self.cargaRed = True
            else:
                self.cragaRed = False
        if "POWER1" in self.mensaje:
            if self.mensaje["POWER1"] == "ON":
                self.rele1 = True
                self.flag = False
                # Guardamos el momento en el que conectamos para obtener el tiempo total al día
                conectado = datetime.datetime.now()
            else:
                self.rele1 = False
                # Sumamos el tiempo que ha estado cargando y lo mostramos
                pp = (datetime.datetime.now() - conectado).seconds
                if pp > 30:
                    tiempo = tiempo + pp
                    logging.info("Tiempo conectado {} segundos".format(pp))

        if "POWER2" in self.mensaje:
            if self.mensaje["POWER2"] == "ON":
                self.rele2 = True
                self.flag = False
            else:
                self.rele2 = False
       # Mostramos el estado del SonOff. Si ponemos el SOCMinimo a 10 continuará cargando indefinidamente
        logging.info(
            "SOC Mínimo {}%, Relé1 = {}, Relé2 = {}, carga = {}, flag = {}, cargaRed = {}, {}".format(self.SOCMinimo, self.rele1, self.rele2, self.carga, self.flag, self.cargaRed, self.mensaje)
        )

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
        global tiempo
        # Nos quedamos con la hora para no saturar de mensajes en la misma hora
        hora = datetime.datetime.now().hour
        mensaje = ""
        # Si ya es por la noche mostramos el total de tiempo conectado durante el día y reiniciamos contador
        if hora == 21 and tiempo > 0:
            logging.info(
                'Ha estado activa la carga durante {} minutos y {} segundos'.format(tiempo/60, tiempo%60)
            )
            tiempo = 0
        # Si no hemos activado el flag de carga o se ha desactivado por falta de consumo, lo avisamos una sola vez y salimos
        if not self.carga:
            if not self.flag:
                logging.info('El flag de carga no está activado')
                self.flag = True
            return
        # Obtenemos los datos de estado de la batería y consumo
        self.pregunta()
        self.pregunta("Consumo")
   	    # Si está activo el relé1, es decir, estamos supuestamente cargando el coche, 
        # pero el consumo no lo refleja, desconectamos el relé y desactivamos la carga
        # No lo podemos hacer con el rele2 puesto que no podemos medir el consumo de la calle
        if self.rele1 and self.consumo < 2000:
            # Por si está negociando el coche esperamos un poco
            self.pregunta("Consumo")
            time.sleep(10)
            if self.consumo > 2000:
                return
            # Apagamos relé y quitamos carga
            self.client.publish("cmnd/CargaCoche/backlog", "Power1 0;Mem1 0")
            logging.info('No hay consumo, por lo que el coche ya está cargado o no conectado. Desconectamos')
            #os.system(
            #    'echo Desconectamos el relé por falta de consumo |mutt -s "No hay consumo {} y batería al {}%  Hector.D.Rguez@gmail.com'.format(self.consumo, self.bateria)
            #)
            # Activamos el flag para no seguir procesando
            self.flag = True
            return
        # Si está activo el relé, la batería está por debajo del 50% y son entre las 8 y las 20
        if self.rele1 and self.bateria <= self.SOCMinimo and hora > config.Inicio and hora < config.Final:
            # Deberíamos de cortar la carga o pasar a la red, dependiendo de
            # lo que hayamos pedido
            # Esto lo controlaremos más adelante usando los dos botones que
            # 	nos ofrece el SonOff Dual para ponerlos externos, seguramente
            # 	en la carcasa del cuadro. Por ahora, solo cargamos de la FV
            self.client.publish("cmnd/CargaCoche/POWER1", "OFF")
            logging.info("Desconectamos el coche al {}%".format(self.bateria))
            # Enviamos un mail comunicando el apagado si no lo hemos enviado antes
            if not hora == self.hora:
                #os.system(
                #    'echo Desconectamos el coche |mutt -s "La batería está al {}%" Hector.D.Rguez@gmail.com'.format(self.bateria)
                #)
                self.hora = hora
                mensaje = "y mandamos correo"
            logging.info("Batería al {}%, desconectamos {}".format(self.bateria, mensaje))
        # Si no está activo el relé y tenemos más del SOC Mínimo + un 15% adicional de batería,
        if (
            self.carga
            and not self.rele1
            and self.bateria >= self.SOCMinimo + 15
            and hora > config.Inicio
            and hora < config.Final
        ):
            # Volvemos a conectarlo
            self.enciende()
            if not hora == self.hora:
                #os.system(
                #    'echo Conectamos el coche |mutt -s "La batería está al {}%" Hector.D.Rguez@gmail.com'.format(self.bateria)
                #)
                self.hora = hora
                mensaje = "y mandamos correo"
            logging.info("Batería al {}%, conectamos {}".format(self.bateria, mensaje))
        # Si estamos cargando de la FV, mostramos el consumo
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
        format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        level=nivel,
    )
    logging.info("Arrancamos el Control de Carga")
    # Inicializamos el objeto para acceder al MQTT
    victron = AccesoMQTT(debug)
    # Tiempo de carga cada día
    tiempo = 0
    conectado = datetime.datetime.now()
    # Nos quedamos en bucle eterno controlando cada 2 minutos
    while True:
        victron.controla()
        time.sleep(120)
