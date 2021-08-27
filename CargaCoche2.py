#! /usr/bin/env python2
# -*- coding: utf-8 -*-
""" Para controlar la carga del coche en función de la batería que existe en 
	el sistema FV y también dependiendo del botón que haya sido apretado en 
	el SonOff Dual R2 del garaje.
	Primer botón: Carga solamente de la FV dependiendo de un SOC mínimo
	Segundo botón: Carga de la FV y si no ha acabado, conmuta a la red 
	después de las 0 horas
    Añadimos también control de potencia máxima, para que no se de el caso 
    de que tenga que tirar de la red cuando estamos cocinando porque el inversor
    más la FV no puedan suministrar toda la potencia necesaria.
	Almacenamos en Mem1 si cargar o no, Mem2 la consigna de SOC Mínimo y en Var3 carga nocturna (1) o cuantas horas (>1):
    %%% Esta información hay que actualizarla al R2
    Programación de botones. Poniendo el weblog a 4 nos cuenta lo siguiente:
    Botón normal: code 0404 enciende, 0405 apaga
    Botón 0: code 0401 enciende, 0400 apaga
    Botón 1: code 0402 enciende, 0403 apaga
    Todos los detecta como Button1 multi-press 1
    *** Parece ser que los botones en pines activan directamente los relés, aunque le programemos una rule.
        El button0 se corresponde realmente con el 2 en la programación, y el 1 con el uno. La diferencia
        es que el botón normal, que también es el uno, si que solo hace lo definido en la rule. A la espera
        de ver si podemos cablear directamente el botón normal, pasamos a programar en la rule la desconexión
        de los relés.
    ***
    %%%
    Configuramos una regla en el SonOff para que cambie el comportamiento de los botones, haga encender el 
    led durante 5 segundos cuando activamos la carga con el botón verde que reinicie las variables, 
    carga de fotovoltaica Mem1 a 1 a las 9. También ponemos el pulsetime2 a 0 y a las 13 apagamos el relé de la red:
    rule1 on button1#state do backlog mem1 1;LedPower1 on;Delay 50;LedPower1 off endon on button2#state do add3 1 endon on time#Minute=540 do backlog mem1 1; pulsetime2 0 endon on time#Minute=780 do power2 off endon
    Y configuramos una segunda regla para hacer parpadear el Led tantas veces como horas hemos programado la carga nocturna con el botón rojo
    rule2 on var3#state>0 do var5 %var3% endon on var5#state>0 do backlog Ledpower1 on;delay 10;ledpower1 off;sub5 1 endon
    Para que no haya problemas con las actualizaciones de las imágenes, tenemos que instalar las librerías
    en nuestro home, para ello creamos una carpeta lib en /home/root y en ella instalamos el Paho-MQTT y
    definimos un .bashrc donde hacemos un 
    export PYTHONPATH=/home/root/lib/
    Y como por alguna extraña razón se empeña en arrancar en sh en vez de bash, creamos un .profile que
    arranca el bash.
    
"""

import time, datetime, sys, json, logging, pytz
import config
import paho.mqtt.client as mqtt

# Definimos una constante con las cadenas para preguntar por MQTT de manera que el código sea más legible
Preguntas = {
    "Bateria": "R/{}/system/0/Dc/Battery/Soc".format(config.VictronInterna),
    "Consumo": "R/{}/system/0/Ac/Consumption/L1/Power".format(config.VictronInterna),
    "FV": "R/{}/system/0/Ac/PvOnOutput/L1/Power".format(config.VictronInterna),
    "Reles": "cmnd/CargaCoche/STATUS",
    "SOCMinimo": "cmnd/CargaCoche/Mem2",
    "CargaRed": "cmnd/CargaCoche/Var3",
    "Carga": "cmnd/CargaCoche/Mem1",
    "Pulse": "cmnd/CargaCoche/PulseTime2",
    "PlacaPulse": "cmnd/placa/PulseTime1"
}
   
class AccesoMQTT:
    """ Para acceder al Venus GX a través de MQTT de cara a gestionar la recarga del coche del sistema FV
    """

    def __init__(self, debug=False):
        self.debug = debug
        # Creo el cliente
        self.client = mqtt.Client("Coche")
        # Conecto al broker. Como cuando se reinicia hemos visto que es posible que el servicio se active 
        # después del programa, ponemos varios reintentos para esperar por el servicio hasta 150 segundos
        # Definimos una variable para chequear desde el control principal del programa si la conexión ha ido bien
        self.noResponde = 0
        activo = -1
        while True:
            try:
                activo = self.client.connect('localhost')
            except:
                self.noResponde += 1
                time.sleep(30)
            if self.noResponde == 5:
                return
            # Cuando la conexión se realiza sin problema devuelve un 0, así que salimos del bucle
            if activo == 0:
                break
        # Asigno la función que va a procesar los mensajes recibidos
        self.client.message_callback_add(
            'N{}'.format(Preguntas["Bateria"][1:]), self.lee_Bateria
        )
        self.client.message_callback_add(
            'N{}'.format(Preguntas["Consumo"][1:]), self.lee_Consumo
        )
        self.client.message_callback_add(
            'N{}'.format(Preguntas["FV"][1:]), self.lee_FV
        )
        self.client.message_callback_add("stat/CargaCoche/STATUS", self.lee_EstadoDual)
        self.client.message_callback_add("stat/CargaCoche/RESULT", self.lee_Result)
        self.client.message_callback_add("stat/placa/RESULT", self.lee_Placa)
        # Me subscribo a los tópicos necesarios, el SOC de la batería, el consumo y el estado del SonOff
        self.client.subscribe(
            [
                ('N{}'.format(Preguntas["Bateria"][1:]), 0),
                ('N{}'.format(Preguntas["Consumo"][1:]), 0),
                ('N{}'.format(Preguntas["FV"][1:]), 0),
                ("stat/CargaCoche/#", 0),
                ("stat/placa/RESULT", 0)
            ]
        )
        # Comenzamos el bucle
        self.client.loop_start()
        # Inicializamos la variable que servirá para que no me mande más de un mensaje a la hora
        self.acs = 0
        self.bateria = 0
        self.hora = 0
        self.carga = True
        self.placa = 0
        self.placaquedan = 0
        self.quedan = 0
        self.rele1 = 0
        self.rele2 = 0
        self.SOCMinimo = 50
        self.cargaRed = False
        self.consumo = 0
        self.tePasaste = False
        self.fv = 0
        self.flag = False
        self.parcial = 0
        # Obtenemos valores
        for f in Preguntas:
            self.pregunta(f)

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
		# Cuando el coche está cargando, mostramos como va la batería
        logging.debug(logtime + "Bateria al {}%, {}".format(self.bateria, self.mensaje))

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
        logging.debug(logtime + "Consumo: {}W, {}".format(round(self.consumo), self.mensaje))
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
        logging.debug(logtime + "Relé1 = {}, Relé2 = {}, {}".format(self.rele1, self.rele2, self.mensaje))
 
    def lee_FV(self, client, userdata, message):
        """ Esta función es llamada para leer la producción de la FV
		"""
        # Lo importamos en formato json
        if self.debug:
            print(message.payload)
        # A veces recibimos mensajes vacíos, así que en ese caso ignoramos,
        # 	puesto que si no obtenemos un error en el json.loads()
        if len(message.payload.decode("utf-8")) == 0:
            return
        self.mensaje = json.loads(message.payload.decode("utf-8"))
        self.fv = self.mensaje["value"]
        logging.debug(logtime + "FV: {}W, {}".format(round(self.fv), self.mensaje))

    def lee_Placa(self, client, userdata, message):
        """ Se encarga de obtener el estado de la placa de ACS y el tiempo que le queda para apagarse
        """
        # Lo importamos en formato json
        self.mensaje = json.loads(message.payload.decode("utf-8"))
        # Asignamos la carga
        if "POWER" in self.mensaje:
            if self.mensaje["POWER"] == "ON":
                self.placa = True
            else:
                self.placa = False
        if "PulseTime1" in self.mensaje:
            self.placaquedan = self.mensaje["PulseTime1"]["Remaining"]
            
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
        # Asignamos la carga de red si la hacemos a mano
        if "Var3" in self.mensaje:
            if self.mensaje["Var3"] == "0":
                self.cargaRed = False
            else:
                self.cargaRed = int(float(self.mensaje["Var3"]))
        # Asignamos la carga de red si la hacemos a través del botón rojo
        if "Add3" in self.mensaje:
            if self.mensaje["Add3"] == "0":
                self.cargaRed = False
            else:
                self.cargaRed = int(float(self.mensaje["Add3"]))
        if "POWER1" in self.mensaje:
            if self.mensaje["POWER1"] == "ON":
                self.rele1 = True
                self.flag = False
                # Si conectamos ponemos a false el flag de haber excedido el consumo máximo
                self.tePasaste = False
                # Guardamos el momento en el que conectamos para obtener el tiempo total al día
                conectado = datetime.datetime.now()
                self.parcial = 0
            else:
                # Cuando activamos el botón producimos un Power Off aunque no estuviera encendido, lo que hace que informe
                # erróneamente del tiempo que llevaba conectado, por lo que antes hacemos una comprobación
                # Si antes estaba encendido procedemos con el tema del tiempo
                if self.rele1:
                    # Sumamos el tiempo que ha estado cargando y lo mostramos
                    self.parcial = (datetime.datetime.now() - conectado).seconds
                    if self.parcial > 120:
                        tiempo = tiempo + self.parcial
                        logging.info(logtime + "Tiempo conectado {} minutos y {} segundos".format(self.parcial/60, self.parcial%60))
                self.rele1 = False

        if "POWER2" in self.mensaje:
            if self.mensaje["POWER2"] == "ON":
                self.rele2 = True
                self.flag = False
            else:
                self.rele2 = False
        # Nos quedamos con lo que queda pendiente hasta apagarse por si se enciende la placa de ACS y tenemos que parar la carga
        if "PulseTime2" in self.mensaje:
            self.quedan = self.mensaje["PulseTime2"]["Remaining"]
                
        # Mostramos el estado del SonOff
        logging.info(logtime + 
            "SOC Mínimo {}%, Relé1 = {}, Relé2 = {}, carga = {}, flag = {}, cargaRed = {}, batería {}%, consumo {}W, FV: {}W, PulseTime2: {}s, ACS: {}, ACSPulse: {}, {}".format(self.SOCMinimo, self.rele1, self.rele2, self.carga, self.flag, self.cargaRed, self.bateria, self.consumo, self.fv, self.quedan, self.placa, self.placaquedan, self.mensaje)
        )

    def mandaCorreo(self, mensaje, asunto = 'Información sobre carga del coche'):
        """ Manda correo al usuario informando del estado
        """
        import smtplib

        # Tenemos que contemplar la posibilidad de que no tengamos Internet en el momento y evitar que casque el programa
        try:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        except BaseException:
            return
        server.login(config.Email, config.Clave)
        de = "CargaCoche <none@none.unk>"
        cuerpo = 'From: {}\nTo: {}\nSubject: {}\n\n{}'.format(de, config.Email, asunto, mensaje)
        server.sendmail(de, config.Email, cuerpo)
        server.close()
        
    def pregunta(self, que="Bateria"):
        """ Manda la petición por MQTT, por defecto, del estado de la batería
		"""
        # Pedimos por MQTT lo solicitado
        self.client.publish(Preguntas[que], "")
        time.sleep(0.5)

    def controla(self):
        """ Controla el estado de la batería y del relé y activa o desactiva 
			en función de la hora y el % de SOC
		"""
        global tiempo
        # Nos quedamos con la hora para no saturar de mensajes en la misma hora. Lo pasamos al main
        #hora = datetime.datetime.now(pytz.timezone('Europe/London')).hour
        mensaje = ""
        # Si ya es por la noche mostramos el total de tiempo conectado durante el día y reiniciamos contador
        if hora == 20 and tiempo > 0:
            logging.info(logtime + 
                'Ha estado activa la carga durante {} minutos y {} segundos'.format(tiempo/60, tiempo%60)
            )
            tiempo = 0
        # Si no está activo el relé de la red, es la hora de empezarla, y cargaRed es > 0 activamos la carga nocturna
        # Ampliamos el horario de comprobación de manera que no solo se active a la hora de InicioRed sino en todo el periodo
        # hasta FinalRed, de esta manera si nos ha faltado carga por la mañana podemos volver a activarla con el botón rojo.
        # Ponemos un and porque ahora la tarifa barata empieza a las 0 horas y el llano ya no es tan barato como antes
        # También cambiamos en el SonOff la rule para que desconecte la carga a las 8 de la mañana, que si no, nos clavan
        if self.cargaRed and not self.rele2 and hora >= config.InicioRed and hora <= config.FinalRed:
            """ Configuramos la carga nocturna dependiendo del valor de Var3
            1: Cargamos hasta que lo desactivemos manualmente
            >1: Horas que vamos a estar cargando usando PulseTime
            """
            pulso = 0
            # Si hemos programado unas horas en concreto:
            if self.cargaRed > 1:
                # Asignamos el valor del pulso en segundos más los 100 primeros que son décimas de segundo
                pulso = (self.cargaRed * 3600) + 100
            # Configuramos el PulseTime
            self.client.publish("cmnd/CargaCoche/PulseTime2", pulso)
            logging.debug(logtime + "Pulso: {}".format(pulso))
            # Encendemos el segundo relé
            logging.info(logtime + "Arrancamos la carga nocturna durante {} horas".format(self.cargaRed))
            self.enciende(False)
            # Procedemos a poner Var3 a 0 para que no se vuelva a activar
            self.client.publish("cmnd/CargaCoche/Var3", 0)
        # Chequeamos si mientras estamos cargando de la red se ha encendido la placa y la batería está por debajo del mínimo absoluto
        if self.rele2 and self.placa and self.bateria <= 10:
            # Vemos cuanto nos falta de tiempo de carga y de la placa
            self.pregunta("Pulse")
            self.pregunta("PlacaPulse")
            # Esperamos un par de segundos a tener la información
            time.sleep(2)
            # Apagamos carga
            self.client.publish("cmnd/CargaCoche/POWER2", "0")
            # Activamos flag
            self.acs = True
            # Y nos quedamos parados hasta que termine de calentar la placa, son 100 menos del tiempo, pero le damos 5 segunditos de margen
            time.sleep(self.placaquedan - 95)
        # Si hemos parado porque se había activado la placa y estaba tirando de la red y ya se ha apagado, volvemos a lanzar la carga
        if self.acs and not self.placa:
            # Programamos el PulseTime2 con el tiempo restante
            self.client.publish("cmnd/CargaCoche/PulseTime2", self.quedan)
            # Encendemos
            self.enciende(False)
            # Reiniciamos variables
            self.acs = 0
            self.quedan = 0
            self.placaquedan = 0
        # Si no hemos activado el flag de carga o se ha desactivado por falta de consumo, lo avisamos una sola vez y salimos
        if not self.carga:
            if not self.flag:
                logging.info(logtime + 'El flag de carga no está activado')
                self.flag = True
            return
        # Obtenemos los datos de estado de la batería, consumo y FV
        self.pregunta()
        self.pregunta("Consumo")
        self.pregunta("FV")
        # Si está activo el relé1, es decir, estamos supuestamente cargando el coche, 
        # pero el consumo no lo refleja, desconectamos el relé y desactivamos la carga
        # No lo podemos hacer con el rele2 puesto que no podemos medir el consumo de la calle
        if self.rele1 and self.consumo < config.PotenciaMinPR:
            # Por si está negociando el coche esperamos un poco
            self.pregunta("Consumo")
            time.sleep(15)
            if self.consumo > config.PotenciaMinPR:
                return
            # Apagamos relé y quitamos carga
            self.client.publish("cmnd/CargaCoche/backlog", "Power1 0;Mem1 0")
            coletilla = ''
            if self.parcial > 120:
                coletilla = ' Tiempo conectado {}:{}'.format(self.parcial/60, self.parcial%60)
            logging.info(logtime + 'No hay consumo, por lo que el coche ya está cargado o no conectado. Desconectamos')
            self.mandaCorreo('Batería al {}%. {}'.format(self.bateria, coletilla), 'Desconectamos por falta de consumo {}'.format(self.consumo))
            # Activamos el flag para no seguir procesando
            self.flag = True
            return
        # Si está activo el relé, la batería está por debajo del SOC Mínimo (Mem2)
        if self.rele1 and self.bateria <= self.SOCMinimo:
            # Deberíamos de cortar la carga o pasar a la red, dependiendo de
            # lo que hayamos pedido
            # Esto lo controlaremos más adelante usando los dos botones que
            # 	nos ofrece el SonOff Dual para ponerlos externos, seguramente
            # 	en la carcasa del cuadro.
            self.client.publish("cmnd/CargaCoche/POWER1", "OFF")
            # Enviamos un mail comunicando el apagado si no lo hemos enviado antes
            time.sleep(1)
            coletilla = ''
            if self.parcial > 120:
                coletilla = ' Tiempo conectado {}:{}'.format(self.parcial/60, self.parcial%60)
            if not hora == self.hora:
                self.mandaCorreo('La batería está al {}%. {}'.format(self.bateria, coletilla), 'Desconectamos el coche')
                self.hora = hora
                mensaje = "y mandamos correo"
            logging.info(logtime + "Batería al {}%, desconectamos {}".format(self.bateria, mensaje))
        # Si está activo el relé pero el consumo es superior al límite impuesto, paramos la carga
        if self.rele1 and self.consumo - self.fv > config.PotenciaMax:
            self.client.publish("cmnd/CargaCoche/POWER1", "OFF")
            time.sleep(1)
            coletilla = ''
            # Activamos flag para poder reiniciar la carga desde que el consumo baje
            self.tePasaste = True
            if self.parcial > 120:
                coletilla = ' Tiempo conectado {}:{}'.format(self.parcial/60, self.parcial%60)
            # Enviamos un mail comunicando el apagado si no lo hemos enviado antes
            if not hora == self.hora:
                self.mandaCorreo('El consumo es de {}W y la FV está dando {}. {}'.format(self.consumo, self.fv, coletilla), 'Desconectamos el coche por exceso de consumo')
                self.hora = hora
                mensaje = "y mandamos correo"
            logging.info(logtime + "Batería al {}%, desconectamos por exceso de consumo: {}, {}".format(self.bateria, self.consumo, mensaje))
        # Si hemos desconectado por exceso de consumo no esperamos a estar por encima del SOC Mínimo + margen y conectamos desde que el consumo baje
        if self.tePasaste and self.bateria > self.SOCMinimo and self.consumo + config.PotenciaPR - self.fv < config.PotenciaMax:
            self.enciende()
            logging.info(logtime + "Volvemos a conectar puesto que ha bajado el consumo y la batería está al {}%".format(self.bateria))
        # Si no está activo el relé y tenemos más del SOC Mínimo + un margen adicional de batería, el consumo es moderado y tenemos suficiente FV
        if self.carga and not self.rele1 and self.bateria >= self.SOCMinimo + config.Margen and self.consumo + config.PotenciaPR - self.fv < config.PotenciaMax and self.fv >= config.PotenciaFVMin:
            # Volvemos a conectarlo
            self.enciende()
            if not hora == self.hora:
                self.mandaCorreo('La batería está al {}%'.format(self.bateria), 'Conectamos el coche')
                self.hora = hora
                mensaje = "y mandamos correo"
            logging.info(logtime + "Batería al {}%, conectamos {}".format(self.bateria, mensaje))
        # Si estamos cargando de la FV, mostramos el consumo
        logging.debug(logtime + "Consumo: {}W".format(self.consumo))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        debug = True
        nivel = logging.DEBUG
    else:
        debug = False
        nivel = logging.INFO
    # Inicializamos el logging
        logging.basicConfig(
        format=" %(message)s",
        level=nivel,
    )
    #    format="%(asctime)s %(message)s",
    #    datefmt="%d/%m/%Y %H:%M:%S",
    logtime = datetime.datetime.now(pytz.timezone('Europe/London')).strftime("%d/%m/%Y %H:%M:%S") + ' '
    logging.info(logtime + "Arrancamos el Control de Carga")
    # Inicializamos el objeto para acceder al MQTT
    victron = AccesoMQTT(debug)
    if victron.noResponde > 1:
        logging.info(logtime + 'Después de 5 intentos, 10 segundos, no hemos conseguido contactar con el servicio de MQTT')
        exit()
    # Tiempo de carga cada día
    tiempo = 0
    conectado = 0
    # Nos quedamos en bucle eterno controlando
    while True:
        dia = datetime.datetime.now(pytz.timezone('Europe/London')).isoweekday()
        hora = datetime.datetime.now(pytz.timezone('Europe/London')).hour
        # Actualizamos el logtime aquí para no tener que llamarlo dentro de Controla, aunque eso creará que todo los logs en la misma iteración salgan con el mismo tiempo
        logtime = datetime.datetime.now(pytz.timezone('Europe/London')).strftime("%d/%m/%Y %H:%M:%S") + ' '
        victron.controla()
        time.sleep(30)
