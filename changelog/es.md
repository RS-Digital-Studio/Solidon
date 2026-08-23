# Novedades

Este archivo es lo que aparece en la ventana de actualización, y nada más.
**No** es una lista de cambios: de 97 commits entre 0.1.1 y 0.1.2 quedan ocho
líneas, y elegirlas es el trabajo. Un punto pertenece aquí si alguien lo nota
al usar el programa.

Por tanto: ni mensajes de commit, ni nombres de módulos, ni números de
apartado. «La barra desaparecía mientras la aplicación seguía calculando
cuatro segundos» es un buen commit y una mala entrada; «El progreso se
mantiene hasta que el cálculo termina de verdad» dice lo mismo a quien está
delante.

Un archivo por idioma en esta carpeta, como en los catálogos, y todos llevan
los mismos puntos en el mismo orden (`tests/test_changelog.py`).
`tools/make_download.py` toma el apartado de la versión actual y lo escribe en
`website/version.json`.

## 0.1.4

- Una pieza seleccionada se mueve directamente con el ratón: agarrar y arrastrar, sin recurrir antes a «Mover». El tirador queda para lo preciso: por ejes y a pasos de rejilla.
- Desde abajo se ve ahora a través de la cama de impresión. Quien trabaja la cara inferior de una pieza gira la vista por debajo y ve la pieza en vez de la placa.
- Un taladro también se puede seleccionar haciendo clic en su interior, no solo en su pared.
- La búsqueda de comandos entiende ahora palabras corrientes: «copiar», «borrar», «abrir» y «colorear» antes no llevaban a ninguna parte, aunque las cuatro existen.
- La búsqueda encuentra también para quien no conoce el término técnico. Al escribir «reforzar», «encajar» o «atornillar» se llega al nervio de refuerzo, al gancho y al agujero de tornillo.
- Dos entradas de menú se llamaban ambas «remallar». Ahora son «Refinar aristas» y «Uniformar triángulos»: la primera divide aristas largas, la segunda iguala los triángulos.
- Los diálogos hablan del «cuerpo exacto» en vez del «cuerpo B-Rep». El conmutador ya usaba esa palabra; nueve descripciones usaban la más pesada.
- Al iniciarse, Solidon comprueba si hay una versión más reciente y la ofrece. Se descarga e instala solo con tu confirmación; puedes desactivarlo en los ajustes.
- Un modelo de lenguaje local puede calcular ahora diez minutos. Antes el chat se rendía a los dos y pedía un informe de error, por un cálculo que simplemente tardaba más.
- Un anillo se reconoce como una sola característica y ya no como tres rebordes superpuestos.
- La entrada «Engrosar superficie» hace ahora lo que promete. Antes desplazaba la superficie.
- El título de la ventana nombra el modelo abierto, aunque todavía no exista un archivo de proyecto.
- Al dibujar, la medida está en la punta de la línea y no en el borde de la ventana.
- Una entrada de menú bloqueada dice ahora por qué lo está. El motivo ya estaba ahí y era invisible.
- Si el cálculo se detiene, se indica en qué paso y por qué.
- El informe de error lleva el estado de la escena: objetos con medidas, características, parámetros y el historial. Así un fallo se reproduce en vez de adivinarse.
- Se han corregido varios cierres inesperados al cerrar ventanas y diálogos.
- El archivo de versión está firmado, y Solidon comprueba la firma antes de ofrecer una actualización.
- La superficie de impresión se llama cama en todas partes y su distribución placa, como la nombran los slicers.

## 0.1.3

- El núcleo exacto ya sabe taladrar: «Taladrar un agujero exacto» trabaja directamente sobre el cuerpo exacto, sin el rodeo por una malla.
- Los redondeos y chaflanes se reconocen con más fiabilidad. Antes, un redondeo se comunicaba a veces como un saliente, con un diámetro que no existía.
- Los ejemplos incluidos ya no saludan con advertencias que no lo son.
- La pantalla de inicio cabe en pantallas pequeñas, sin desplazamiento.
- Una característica seleccionada se colorea a sí misma. Antes, todo el cuerpo tomaba el color de selección y no se veía a qué se refería.
- El árbol de objetos indica la medida de cada característica reconocida.
- Las mallas exportadas ya no contienen triángulos vacíos.
- Guardar dos veces da dos veces el mismo archivo.
- Se han revisado las cinco traducciones. Los términos técnicos se llaman ahora como los llaman los slicers.
- La barra de herramientas está ordenada: el campo más ancho era el que menos se necesita.
- Un segundo error del programa ya no coloca una segunda ventana sobre la primera.

## 0.1.2

- Los números decimales escritos se leen bien en todas partes. «12,5» sigue siendo doce y medio; antes podía convertirse en 125, sin preguntar y sin avisar.
- Cada uno de los cincuenta y seis campos de los ajustes de impresión dice ahora qué hace cuando se mueve.
- El tiempo de impresión y el material se estiman con más precisión, sobre todo en piezas ahuecadas.
- La entrega al slicer cae sobre la placa. Con CuraEngine las piezas quedaban al lado.
- Al dividir con pasadores, los agujeros correspondientes quedan en la mitad correcta.
- Milímetros y pulgadas valen ahora allí donde hay un número, también en las barras de herramientas y al pintar.
- El progreso se mantiene hasta que el cálculo termina de verdad, y la ventana sigue siendo utilizable mientras tanto.
- Todos los atajos de teclado están ahora en un único resumen: en el menú Ayuda, bajo «Atajos de teclado», o pulsando la tecla de interrogación.
