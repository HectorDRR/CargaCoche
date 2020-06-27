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

2020-06-27, Ver. 0.5: Implementada la carga diurna incluyendo la consulta del consumo para desconectar el relé en caso de que no
					haya consumo por que no haya ningún coche enchufado.
