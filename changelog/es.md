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

## 0.2.0

- Bloques propios sin una línea de código: seleccione pasos del historial y colóquelos en el catálogo como bloque — con campos propios, vista previa y rango de valores comprobado.
- Un bloque creado por usted viaja dentro del archivo de proyecto. Quien lo abra puede insertar su pieza sin tener que instalar nada.
- Seis bloques nuevos en el catálogo: gancho para panel perforado, soporte de pared, escuadra, pie, clip para cables y ojal de bisagra.
- El gancho para panel aguanta ahora aunque alguien levante la pieza al retirar algo — una lengüeta elástica encaja detrás del panel. Desactivable si retira la pieza a menudo.
- Una cara seleccionada cuenta: taladro, bloque y boceto van adonde usted señaló. Antes cada operación sobre una cara costaba dos clics.
- Al dibujar, la retícula muestra a qué se ajusta, el paso se puede escribir, las medidas están junto al puntero y la barra dice sobre qué cara dibuja.
- En el historial se pueden seleccionar varios pasos a la vez.
- Los límites de una medida se pueden cambiar después — hasta ahora valía para siempre lo que se introdujo al crearla.
- La estimación de material para soportes estaba equivocada por un factor grande: calculaba la superficie bajo el saliente en vez de la columna debajo.
- El avellanado solo funcionaba en un sentido por eje. Seleccionado desde el lado equivocado no quitaba nada y no decía nada.
- En piezas escalonadas, taladro y tapón trabajaban en el aire: la dirección venía de la caja envolvente en vez del material en ese punto.
- Un tapón pasante rellenaba solo la mitad del taladro — y dejaba alrededor la holgura con la que el taladro se había ensanchado para el material.
- El relleno de rejilla colocaba barras junto a la pieza en vez de dentro de su hueco.
- Una rosca en un taladro seleccionado cortaba solo su mitad inferior. Lo mismo ocurría con la bucha de inserción.
- El alojamiento de tuerca y el hueco para la cabeza del tornillo no quitaban nada: ambos construían sobre la cara en vez de debajo.
- Una pieza más delgada que una capa impresa ya no se pone de canto.
- La división automática cuenta el saliente del pasador para el límite de la mesa y no deja ajustes que apunten a sitios desaparecidos.
- Una cavidad hecha desde un dibujo con agujero conserva el agujero. Hasta ahora fresaba también la isla.
- Al hacer clic en un taladro se propone el tornillo que realmente pasa por él — y se indica el diámetro medido.
- Un archivo de un slicer llegaba con cuerpos duplicados: una pieza con diecisiete objetos se leía diecisiete veces, con el doble de volumen y el doble de tiempo de impresión.
- Al escalar a una anchura dada se medía también una línea auxiliar. De cincuenta milímetros salían cinco.
- Al exportar, piezas con el mismo nombre se sobrescribían: un archivo, dos mensajes de éxito, una pieza perdida.
- Un cambio de idioma surte efecto en toda la ventana. Los ajustes de impresión se quedaban en el idioma con el que se inició la aplicación.
- Un cambio de impresora o material conserva lo que usted ajustó. Hasta ahora se restablecía todo el conjunto sin avisar.
- La elección de filamento por ranura de material llega al slicer. Antes se guardaba el texto mostrado en vez del perfil.
- Un proyecto modificado ya no se pierde al arrastrar un archivo a la pantalla de inicio — se pregunta antes.
- Una propuesta del chat que retira pasos dice de antemano cuáles se van con ella. Y Cancelar cancela de verdad, en vez de seguir calculando en segundo plano.
- Un reloj mal ajustado ya no se lleva la demo: un ordenador con la fecha en el futuro quemaba el plazo para siempre.
- Quien tiene licencia ya no recibe una invitación a comprar cuando un archivo del programa está dañado, sino que se entera de lo que pasa realmente.
- Un archivo de proyecto de otra persona avisa antes del primer cálculo si trae código fuente para un programa externo — por cualquier vía y a cualquier profundidad.


## 0.1.5

- Ahora se dibuja en la propia vista: la superficie de dibujo se coloca sobre el modelo en lugar de sustituirlo, y un clic en la vista sitúa un punto en el plano del boceto.
- La cuadrícula de la superficie de dibujo vuelve a mostrar aquello a lo que se ajusta. Estuvo un tiempo en una décima de milímetro y quedaba medio oculta tras la barra.
- Un clic en el centro de un taladro selecciona el taladro. Antes acertaba en la cara contigua o en nada, y en la vista superior incluso anulaba la selección.
- Un clic dentro de un recorte rectangular selecciona la pieza en lugar de anular la selección.
- El chat encuentra ahora su modelo local escriba la dirección como la escriba. Hasta ahora tenía que ser la dirección completa terminada en /api/chat.
- Una clave de acceso que el proveedor rechaza ya no bloquea su modelo local. El chat pasa por sí mismo al siguiente modelo disponible en lugar de enviar de nuevo la misma clave.
- Los mensajes de error del chat dicen ahora a qué modelo se refieren. Sobre un error de clave solo ponía que el modelo de lenguaje no había respondido.
- El campo de la dirección de un servicio ofrece un ejemplo y advierte de que ahí no va una carpeta. Si introduce una, lo recupera con el motivo encima.
- El diálogo de configuración ya no se cierra con error cuando un campo de dirección contiene una ruta de carpeta o el campo de clave un texto pegado por descuido.
- Los menús desplegables vuelven a mostrar todas sus entradas. En cuanto un campo tenía el foco del teclado, al menú abierto le faltaba media entrada.
- Ctrl+Z y Ctrl+Y aparecen ahora en su entrada de menú, como los otros catorce atajos. Siempre funcionaron; simplemente nada los nombraba.
- Los mensajes de error al dibujar indican qué límite se ha superado. Sobre «entre tres y sesenta y cuatro esquinas» solo ponía «La entrada no se podía usar así».
- Las acciones unificadas están en el mismo menú y aparecen una sola vez en la búsqueda de comandos, como vaciar y vaciar con exactitud.
- Una entrada de menú llamada «Rosca» dice ahora dónde va la rosca: en un taladro o sobre un perno.
- La interfaz en español nombra los rasgos igual en todas partes. En la misma lista había antes dos palabras para lo mismo.
- La aplicación libera memoria al cerrar una ventana y termina de forma más limpia.
- La imagen que acompaña a un comentario muestra ahora también el modelo. Antes había en el centro una superficie negra, justo donde está la pieza de la que se trata.


## 0.1.4

- Durante la demo, Solidon pregunta una vez: tras media hora de trabajo, una tarjeta se posa sobre la vista y pregunta qué tal va. No detiene nada, y sin su clic no sale nada.
- Al hacer clic en una cara e insertar un elemento, este queda perpendicular a esa cara en lugar de apuntar hacia arriba. En una pared lateral, un agujero para tornillo quedaba antes atravesado.
- Un elemento colocado en un taladro adopta su medida. En un taladro de 5,19 mm, el casquillo a presión proponía antes M3, que allí no quita nada.
- Un clic con la mano algo temblorosa vuelve a seleccionar en vez de desplazar la pieza una décima de milímetro.
- Una pieza seleccionada se mueve directamente con el ratón: agarrar y arrastrar, sin recurrir antes a «Mover». El tirador queda para lo preciso: por ejes y a pasos de rejilla.
- Desde abajo se ve ahora a través de la cama de impresión. Quien trabaja la cara inferior de una pieza gira la vista por debajo y ve la pieza en vez de la placa.
- Un taladro también se puede seleccionar haciendo clic en su interior, no solo en su pared.
- La búsqueda de comandos entiende ahora palabras corrientes: «copiar», «borrar», «abrir» y «colorear» antes no llevaban a ninguna parte, aunque las cuatro existen.
- La búsqueda encuentra también para quien no conoce el término técnico. Al escribir «reforzar», «encajar» o «atornillar» se llega al nervio de refuerzo, al gancho y al agujero de tornillo.
- Dos entradas de menú se llamaban ambas «remallar». Ahora son «Refinar aristas» y «Uniformar triángulos»: la primera divide aristas largas, la segunda iguala los triángulos.
- El programa habla el idioma que usted oye en otras partes: «cuerpo exacto» en vez de «B-Rep», cama en vez de superficie de impresión, placa para la distribución.
- Al iniciarse, Solidon comprueba si hay una versión más reciente y la ofrece. Se descarga e instala solo con tu confirmación; puedes desactivarlo en los ajustes.
- Un modelo de lenguaje local puede calcular ahora diez minutos. Antes el chat se rendía a los dos y pedía un informe de error, por un cálculo que simplemente tardaba más.
- Un anillo se reconoce como una sola característica y ya no como tres rebordes superpuestos.
- La entrada «Engrosar superficie» hace ahora lo que promete. Antes desplazaba la superficie.
- El título de la ventana nombra el modelo abierto, aunque todavía no exista un archivo de proyecto.
- Al dibujar, la medida está en la punta de la línea y no en el borde de la ventana.
- Una entrada de menú bloqueada dice ahora por qué lo está. El motivo ya estaba ahí y era invisible.
- El informe de error lleva el estado de la escena: objetos con medidas, características, parámetros y el historial. Así un fallo se reproduce en vez de adivinarse.
- Se han corregido varios cierres inesperados al cerrar ventanas y diálogos.

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
