# Logs de ejecución

El logger genera un archivo `.log` nuevo por ejecución con timestamp y niveles
INFO, WARNING y ERROR. Los logs operativos siguen ignorados mediante `logs/*`;
solo se exceptúan `.gitkeep`, este README y el ejemplo específico enlazado abajo.
No se modifica el logger ni se registra una ejecución nueva en este cierre.

## Copia histórica real

[etl_20261007_223144_ejemplo.txt](etl_20261007_223144_ejemplo.txt) es una
**COPIA HISTÓRICA** byte a byte de [carga_real.txt](../evidencias/carga_real.txt),
correspondiente a la carga iniciada el 2026-10-07 a las 22:31:44.
La etiqueta está aquí, no añadida al archivo, para preservar sus bytes.
Se revisaron sus mensajes: contienen tareas, conteos, destino relativo y tiempos,
sin URI, credenciales ni documentos de Airbnb.

Tamaño: 163.995 bytes. SHA256 de ambas copias:
`4bb905687030992e09c6216b7967538d437601598f72800b49926aec6c41e727`.
El ejemplo no prueba una ejecución actual ni sustituye los logs nuevos.
