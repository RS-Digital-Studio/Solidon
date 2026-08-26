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


### Bloques
- Bloques propios sin una línea de código: seleccione pasos del historial y colóquelos en el catálogo como bloque — con campos propios, vista previa y rango de valores comprobado.
- Un bloque creado por usted viaja dentro del archivo de proyecto. Quien lo abra puede insertar su pieza sin tener que instalar nada.
- Cinco bloques nuevos en el catálogo: gancho para panel perforado, escuadra, pie, clip para cables y ojal de bisagra.
- El gancho para panel aguanta ahora aunque alguien levante la pieza al retirar algo — una lengüeta elástica encaja detrás del panel. Desactivable si retira la pieza a menudo.
- Soporte de pared, nervadura, lengüeta y ranura, pestaña, unión de encaje y bisagra de película aparecen ya en el menú de una cara pulsada. Faltaba justo el soporte de pared.
- Quien inserta un bloque del catálogo sin elegir un sitio recibe ahora una pregunta. Hasta ahora se colocaba en el origen, mitad dentro de la pieza y mitad bajo la placa.
- El catálogo de bloques se puede consultar incluso sin modelo. Insertar queda entonces bloqueado y dice por qué, en vez de cancelar solo tras confirmar.
- El alojamiento de tuerca y el hueco para la cabeza del tornillo no quitaban nada: ambos construían sobre la cara en vez de debajo.
- El alojamiento de imán vuelve a sujetar el imán: el labio de retención se añadía antes al alojamiento en vez de vaciarse en él, y desaparecía dentro.
- La ranura de ojo de cerradura cuelga ahora en vertical, de modo que el tornillo se atasca al descender. Tumbada de lado, se desplazaba hacia un costado y la cabeza no encontraba sitio.
- El alojamiento de tuerca encaja ahora con la tuerca: para M5, M6 y M8 la tabla tenía una altura demasiado pequeña, en M5 seis décimas de menos.

### Dibujo
- Al dibujar, la retícula muestra a qué se ajusta, el paso se puede escribir, las medidas están junto al puntero y la barra dice sobre qué cara dibuja.
- Los atajos de teclado vuelven a funcionar en el modo de dibujo — línea, círculo, arco, recortar, desfase, Ctrl+Z — y el clic derecho abre el menú del dibujo en vez del modelo.
- Ajustar a la vista devuelve el dibujo al encuadre, y un clic a cinco milímetros de un punto ya no se ajusta a él.
- Una línea auxiliar sigue siendo una línea auxiliar, incluso tras recortarla, alargarla, desfasarla o reflejarla. Hasta ahora una línea de centro se convertía en arista de perfil y partía la pieza.
- El diálogo de un paso muestra las medidas de su dibujo en vez de los valores predeterminados, y un círculo aparece con su diámetro completo, no con la mitad.
- Una cavidad hecha desde un dibujo con agujero conserva el agujero. Hasta ahora fresaba también la isla.
- Un agujero dibujado se resta sin importar en qué sentido lo dibujó. Según el orden de los clics salía antes una pieza más llena.
- Recortar corta ahora solo dentro de su propio tramo, y Alargar también encuentra círculos y arcos como destino — hasta ahora solo veía líneas.
- Una transición entre dos dibujos conserva sus agujeros, y un vaciado en una pared lateral corta en la pared en vez de desde arriba.
- Un contorno que se cruza consigo mismo se señala ahora en el dibujo, en vez de producir un cuerpo que no es estanco y aun así se exporta.
- Un dibujo con agujero dentro de agujero conserva todos los niveles, y Proyectar toma el plano en el que dibuja — hasta ahora se perdía el tercer nivel y el corte venía desde abajo.
- Al escalar a una anchura dada se medía también una línea auxiliar. De cincuenta milímetros salían cinco.

### Historial y pasos
- En el historial se pueden seleccionar varios pasos a la vez.
- Los límites de una medida se pueden cambiar después — hasta ahora valía para siempre lo que se introdujo al crearla.
- Cambiar un paso después ahora se puede deshacer. Hasta ahora Ctrl+Z eliminaba la acción equivocada y dejaba en pie el valor cambiado.
- Un paso que apunta a una cara de otro cuerpo se vuelve a calcular tras cada cambio. Hasta ahora una pieza alineada se quedaba en el sitio antiguo, incluso tras cerrar.
- Las características conservan su nombre cuando una pieza se gira o desplaza para imprimir. Los pasos y ajustes que las señalan ya no apuntan al vacío.
- Si desaparece la cara hasta la que se extruye, el error señala ahora ese campo y sugiere elegir otra — en vez de señalar el plano del boceto.

### Herramientas y geometría
- El avellanado solo funcionaba en un sentido por eje. Seleccionado desde el lado equivocado no quitaba nada y no decía nada.
- En piezas escalonadas, taladro y tapón trabajaban en el aire: la dirección venía de la caja envolvente en vez del material en ese punto.
- Un tapón pasante rellenaba solo la mitad del taladro — y dejaba alrededor la holgura con la que el taladro se había ensanchado para el material.
- El relleno de rejilla colocaba barras junto a la pieza en vez de dentro de su hueco.
- El orificio de ventilación de una pieza vaciada termina ahora en el hueco en vez de atravesar la tapa, y la ranura roscada de la tapa giratoria ya no abre un agujero en su propia parte superior.
- Unir, restar y pintar avisan ahora cuando no ha ocurrido nada. Hasta ahora un paso permanecía en el historial sobre un modelo sin cambios.
- Si una pieza se rompe porque un bloque ya no toca su soporte, el informe lo señala ahora como error y recomienda qué hacer. Hasta ahora el número de trozos era solo un dato.
- Una rosca en un taladro seleccionado cortaba solo su mitad inferior. Lo mismo ocurría con la bucha de inserción.
- Una rosca interior se resta ahora, tal como dice su nombre. Hasta ahora crecía en su lugar un perno dentro del taladro de núcleo.

### Impresión y slicer
- La estimación de material para soportes estaba equivocada por un factor grande: calculaba la superficie bajo el saliente en vez de la columna debajo.
- La anchura de puente mide ahora el tramo que realmente se salva sin apoyo. Un canal de cables informaba antes de la anchura de su caja envolvente y recibía el consejo equivocado.
- Una pieza más delgada que una capa impresa ya no se pone de canto.
- La división automática cuenta el saliente del pasador para el límite de la mesa y no deja ajustes que apunten a sitios desaparecidos.
- Los conjuntos también responden ya a «Posar sobre la cama»: bajan como un todo y las piezas conservan su posición relativa. Hasta ahora no pasaba nada, sin aviso.
- La cantidad de filamento leída de un archivo G-code vuelve a ser correcta. Un comando al final del archivo hacía que todo lo anterior se calculase distinto y duplicaba el total.
- Un cambio de impresora o material conserva lo que usted ajustó. Hasta ahora se restablecía todo el conjunto sin avisar.
- La elección de filamento por ranura de material llega al slicer. Antes se guardaba el texto mostrado en vez del perfil.

### Vista y manejo
- Una cara seleccionada cuenta: taladro, bloque y boceto van adonde usted señaló. Antes cada operación sobre una cara costaba dos clics.
- Al hacer clic en un taladro se propone el tornillo que realmente pasa por él — y se indica el diámetro medido.
- Tras «Desplazar cara» las caras de la pieza vuelven a poder pulsarse. Hasta ahora no quedaba nada sobre lo que dibujar, taladrar o poner un ajuste.
- Al abrir un proyecto aparece de inmediato un indicador de carga. Hasta ahora el centro de la ventana quedaba negro varios segundos o mostraba la pantalla de inicio — parecía un cuelgue.
- Un clic en la vista solo acierta ahora en lo que realmente ve — ninguna pieza oculta ni de otra placa. Y tras pasar por el modo Mover, las aristas ya no se ven a través de todas las caras.
- Las vistas de eje de Ctrl+0 a Ctrl+6 vuelven a encuadrar el modelo, en vez de incluir también la placa y el volumen de impresión.
- Quien ha desplazado mucho una pieza y luego la gira, gira de nuevo alrededor de la pieza y no de un punto al lado.
- Una medida en la vista usa ahora la unidad elegida, un cambio de tema recolorea también la placa y el volumen de impresión, y con varias placas la etiqueta y el asa quedan en la pieza, no al lado.
- Lo que trae consigo un bloque insertado figura en el árbol de objetos bajo su nombre, y el nodo ofrece modificar precisamente ese paso.
- La sombra bajo la pieza muestra ahora cada trozo por separado y es más discreta. Si un cuerpo se rompe, ahora se ve en la sombra.

### Archivos y exportación
- Dos archivos importados con el mismo nombre ya no se pierden. El segundo sobrescribía antes al primero, y el proyecto ya no se podía abrir después.
- Una dirección sin extensión de archivo dice ahora que allí hay una página web y dónde está el botón de descarga, en vez de «Formato no reconocido».
- Al exportar, piezas con el mismo nombre se sobrescribían: un archivo, dos mensajes de éxito, una pieza perdida.
- La extensión de proyecto se añade ahora con «Guardar como». Un proyecto guardado como soporte.stl era, al abrirlo, un modelo ajeno ilegible.
- Un proyecto modificado ya no se pierde al arrastrar un archivo a la pantalla de inicio — se pregunta antes.

### Velocidad y estabilidad
- La aplicación ya no desaparece sin avisar cuando se cambia una medida, se lee un dibujo o se calcula un corte. Los mismos cálculos van ahora hasta sesenta veces más rápido.
- Vaciar y colocar espigas se pueden cancelar de verdad. En una pieza escaneada, el botón se quedaba quieto minutos enteros.
- Los archivos grandes de un slicer se abren con soltura, sin que la ventana se congele. Antes, el mero recuento de cuerpos leía todo el archivo en memoria.
- Si un cálculo en segundo plano se queda atascado, la aplicación ahora lo dice. Si no, la leyenda, el análisis de capas y la búsqueda de una versión nueva se quedaban parados para siempre.
- Cancelar descarta ahora también la siguiente ejecución ya en cola, y la barra de progreso ya no desaparece sobre un archivo que aún se está escribiendo.

### Idiomas
- El idioma elegido en el instalador se aplica de inmediato, o el del sistema en su defecto. Y un idioma elegido en la ventana surte efecto al momento, no solo al reiniciar.
- Un cambio de idioma surte efecto en toda la ventana. Los ajustes de impresión se quedaban en el idioma con el que se inició la aplicación.
- Los ejemplos incluidos nombran ahora sus medidas en su idioma. Antes ponía «Breite, Tiefe, Höhe» en alemán, incluso con la interfaz en inglés.
- La línea de comandos habla ahora el idioma configurado. Hasta ahora daba ayuda y mensajes de error en alemán, fuera cual fuera la elección.

### Chat y soporte
- Una propuesta del chat que retira pasos dice de antemano cuáles se van con ella. Y Cancelar cancela de verdad, en vez de seguir calculando en segundo plano.
- El chat vuelve a lograr ocho pasos por pregunta en vez de cuatro, y la línea de coste ya no calcula de más.
- Lo que se envía con una respuesta al soporte se muestra antes, palabra por palabra, incluido el registro. Y si no llega, el mensaje da el motivo real.

### OpenSCAD
- Las formas libres ya no necesitan un segundo programa: lo que hacía OpenSCAD lo hacen las herramientas de dibujo y los bloques — una instalación menos de la que ocuparse.
- Un proyecto con código de OpenSCAD se sigue abriendo y todo lo demás se calcula como antes. El Informe nombra el paso, y «Mostrar los valores» copia su código.

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
