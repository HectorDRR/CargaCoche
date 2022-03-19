CargaCoche

Implementar en un Venus GX/ColorControl GX un algoritmo para permitir cargar un VE (Vehículo Eléctirco) a partir de un SOC mínimo.

Usaremos un SonOff Dual R2 con el firmware Tasmota, conectado a dos contactores, el primero suministra corriente del sistema 
fotovoltaico, mientras que el segundo estará directamente conectado a la red de la calle para cargas nocturnas en el caso 
de que no baste con la carga diurna.

Este SonOff Dual tiene la opción de conectarle dos pulsadores, que usaremos para elegir el tipo de carga: 
	El primer pulsador significa que cargaremos solo con la energía que exceda del SOC Mínimo elegido y guardado en el Mem2 
	del Sonoff.
	El segundo pulsador significa que aparte de cargar con los excedentes del día, también cargaremos de madrugada aprovechando
	las tarifas más baratas de la noche, por defecto, de 0 de la mañana hasta las 8, excepto en findes que es durante todo el día.

Tendremos que habilitar el servidor MQTT del Venus/ColorControl GX y redireccionar allí al SonOff.

Dependencias externas:
	- Librería Paho-MQTT
	- Librería pytz para usar la hora local y no tocar la configuración horaria en UTC del Venus
	- Mutt para el envío de correos al usuario.

Historia:

2022-03-19, Ver. 1.3: Empezamos a documentar todos los pasos necesarios para su implementación en otro sistema. Hasta ahora me 
    he limitado a ir haciendo configuraciones en mis equipos, pero ahora me ha surgido la posibilidad de que un compañero con
    un Kona y un sistema similar al mío también se lo quiera implementar, por lo que aprovechamos para revisar todos los pasos
    de configuración necesarios para una puesta en marcha desde el principio. Para ello, añadiremos un fichero config.html al
    repositorio y las imágenes pertinentes para intentar facilitar la configuración del Venus GX/ColorControl y del SonOff, 
    así como el fichero de configuración del SonOff basado en el Tasmota 11.0 para que aplicándolo ya queden configurados los
    parámetros principales.
    
2021-08-28, Ver. 1.2: Implementamos la carga continua para los fines de semana. Esto nos permite poner a cargar de red cuando
	no tenemos suficiente batería y FV y poder cambiar de uno a otro automáticamente en caso de tener suficiente FV. En algunos
	casos tenemos que cargar el coche si o si. Esta opción nos permite hacerlo sin estar pendientes y aprovechar la FV que 
	tengamos disponible, y cuando no, tirar de red aprovechando que los findes es horario valle.

2021-04-06, Ver. 1.1: Después de bastante tiempo funcionando de manera estable, añadimos también la funcionalidad de parar
	la carga nocturna en caso de que se active la placa de ACS y ésta tenga que tirar también de la red, y esperamos hasta que
	termine para volver a lanzar la carga nocturna por el tiempo restante.
	También hemos hecho que se puedan programa x horas de carga nocturna según las veces que apretamos el botón, asi como 
	mostrar a través del led del SonOff la actividad de los dos botones.</p>

2020-08-18, Ver. 0.9: Se ha implementado la carga nocturna permitiendo definir el número de horas que queremos que esté 
	funcionando (Mem3). Se ha implementado también el control de potencia para no exceder la del Inversor + FV cuando estamos 
	cargando debido a algún pico de consumo. También hemos puesto un mínimo de potencia FV para no ciclar la batería en exceso
	así como una consigna de potencia de consumo por debajo de la cual consideramos que el coche ha terminado de cargar.
	Todos los parámteros se establecen en el config.py que se lee al arrancar el programa.
	También llevamos un control del tiempo que se ha estado cargando durante el día indicando el total en el log a las 21 horas.
	Creamos en /data un fichero rcS.local para que cuando haya actualizaciones de firmware o se reinicie el venus arranque la 
	aplicación de manera automática, el contenido del fichero es el siguiente comando:<br>
	#!/bin/sh</br>
	screen -AdmL -Logfile /tmp/Carga.log -S CargaCoche -h 20000 /home/root/lib/CargaCoche2.py</br>
	exit 0</p>

2020-06-27, Ver. 0.5: Implementada la carga diurna incluyendo la consulta del consumo para desconectar el relé en caso de que no
	haya consumo por que no haya ningún coche enchufado.
