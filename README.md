CargaCoche

Implementar en un Venus GX/ColorControl GX un algoritmo para permitir cargar un VE (Vehículo Eléctirco) a partir de un SOC mínimo.

Usaremos un SonOff Dual con el firmware Tasmota, conectado a dos contactores, el primero suministra corriente del sistema 
fotovoltaico, mientras que el segundo estará directamente conectado a la red de la calle para cargas nocturnas en el caso 
de que no basta con la carga diurna.

Este SonOff Dual tiene la opción de conectarle dos pulsadores, que usaremos para elegir el tipo de carga: 
	El primer pulsador significa que cargaremos solo con la energía que exceda del SOC Mínimo elegido y guardado en el Mem2 
	del Sonoff.
	El segundo pulsador significa que aparte de cargar con los excedentes del día, también cargaremos de madrugada aprovechando
	las tarifas más baratas de la noche, por defecto, de 1 de la mañana en adelante.

Tendremos que habilitar el servidor MQTT del Venus/ColorControl GX y redireccionar allí al SonOff.

Lo hemos desarrollado en Python2 para aprovechar lo que ya hay instalado en el Venus/ColorControl GX.

Es necesario instalar la librería Paho-MQTT para su correcto funcionamiento así como el mutt para el envío de correos al usuario.

Historia:

2021-04-06, Ver. 1.1: Después de bastante tiempo funcionando de manera estable, añadimos también la funcionalidad de parar 
	la carga nocturna en caso de que se active la placa de ACS y ésta tenga que tirar también de la red, y esperamos hasta que
	termine para volver a lanzar la carga nocturna por el tiempo restante.
	También hemos hecho que se puedan programa x horas de carga nocturna según las veces que apretamos el botón, asi como 
	mostrar a través del led del SonOff la actividad de los dos botones.
2020-08-18, Ver. 0.9: Se ha implementado la carga nocturna permitiendo definir el número de horas que queremos que esté 
	funcionando (Mem3). Se ha implementado también el control de potencia para no exceder la del Inversor + FV cuando estamos 
	cargando debido a algún pico de consumo. También hemos puesto un mínimo de potencia FV para no ciclar la batería en exceso
	así como una consigna de potencia de consumo por debajo de la cual consideramos que el coche ha terminado de cargar.
	Todos los parámteros se establecen en el config.py que se lee al arrancar el programa.
	También llevamos un control del tiempo que se ha estado cargando durante el día indicando el total en el log a las 21 horas.
	Creamos en /data un fichero rcS.local para que cuando haya actualizaciones de firmware o se reinicie el venus arranque la 
	aplicación de manera automática, el contenido del fichero es el siguiente comando:
	#!/bin/sh
	screen -AdmL -Logfile /tmp/Carga.log -S CargaCoche -h 20000 /home/root/lib/CargaCoche2.py
	exit 0
2020-06-27, Ver. 0.5: Implementada la carga diurna incluyendo la consulta del consumo para desconectar el relé en caso de que no
	haya consumo por que no haya ningún coche enchufado.
