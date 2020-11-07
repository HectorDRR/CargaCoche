# -*- coding: utf-8 -*-
""" Configuración de variables del sistema
"""
# Referencia interna de nuestra instalación, necesaria para conocer el estado de la batería y del consumo
VictronInterna = 'xxxxxxxxxxx'
# Dirección IP del Venux/ColorControl GX en caso de que el programa se use en otro equipo. En caso contrario dejar el actual
Venus = 'localhost'
# Dirección de Email a donde mandar los correos de estado
Email = 'Hector.D.Rguez@gmail.com'
# Clave del correo
Clave = ""
# Hora de comienzo (-1 en verano por llevar UTC el Venus GX)
Inicio = 10
# Hora de final de carga FV
Final = 19
# Hora de inicio de carga de Red
InicioRed = 23
# Hora de finalización de carga de Red
FinalRed = 9
# Potencia pico que no se quiere sobrepasar. En nuestro caso, la que da el inversor de las baterías y al que sumaremos la que dan las placas
PotenciaMax = 4300
# Potencia que usa el PR
PotenciaPR = 3000
# Potencia mínima cuando usamos el PR. Para que corte en caso de cosiderar que el coche ya no está cargando
PotenciaMinPR = 1100
# Potencia que produce la FV mínima para que nos salga a cuenta conectar el coche y no nos limitemos a ciclar la batería
PotenciaFVMin = 500
# Margen de batería (%) sobre el SOC Mínimo para comenzar la carga
Margen = 20
