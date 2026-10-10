# Novedades

Este archivo es lo que aparece en la ventana de actualización, y nada más.
**No** es una lista de cambios, sino una selección, y elegir es el trabajo. Un
punto pertenece aquí si alguien lo nota al usar el programa. Cuántos sean lo
decide la versión, no una cifra.

Por tanto: ni mensajes de commit, ni nombres de módulos, ni números de
apartado. «La barra desaparecía mientras la aplicación seguía calculando
cuatro segundos» es un buen commit y una mala entrada; «El progreso se
mantiene hasta que el cálculo termina de verdad» dice lo mismo a quien está
delante.

Un archivo por idioma en esta carpeta, como en los catálogos, y todos llevan
los mismos puntos en el mismo orden (`tests/test_changelog.py`).
`tools/make_download.py` toma el apartado de la versión actual y lo escribe en
`website/version.json`.

## 0.6.0

### Manejo y sistema

- La demo funciona ahora hasta el 30 de noviembre de 2026. Solidon3D 1.0 está prevista para el 1 de diciembre y sus proyectos se conservan.
- En el Mac, Solidon necesita ahora macOS 14 o más reciente. Cualquier Mac desde 2018 puede instalarlo gratis.
- Solidon ya arranca en los Mac con Intel y macOS 26. La versión 0.5.3 se quedaba colgada allí al iniciar.
- En el Mac, *Cancelar* detiene al instante una respuesta en curso del modelo local.
- En el Mac, Retorno abre la entrada seleccionada en la pantalla de inicio, en *Buscar función* y en el informe de comprobación.
- En Linux, la escritura con Fcitx5 e IBus llega ahora al campo de texto también en el Flatpak y en el AppImage.
- La desinstalación en Windows no deja en el registro entradas de la asociación de archivos.
- Supr también funciona cuando la pestaña *Selección* tiene el foco, y quita varios cuerpos marcados en un solo paso. Si la tecla no hace nada, la barra de estado dice por qué.
- El clic derecho en los cuerpos ofrece *Quitar objeto* y, con varios, *Unir*. *Vaciar* también está en una cara seleccionada, que pasa a ser la abertura.
- Los paneles de la izquierda y la derecha se mueven por su asa, se acoplan a un borde o quedan flotando. *Vista → Paneles a su sitio* los devuelve.
- Los paneles también se pueden colocar abajo a la izquierda, abajo a la derecha y en el borde inferior.
- Puede reordenar las pestañas y arrastrarlas a ventanas propias, también en otra pantalla. Cerrar la ventana o *Volver a Solidon* devuelve su contenido.
- Solidon recuerda la disposición. Las ventanas siguen al alcance aunque se desconecte una pantalla.
- Mientras recalcula, el informe de comprobación dice *Recalculando …* y muestra las líneas anteriores como estado previo. Antes, los errores viejos parecían seguir vigentes.
- Si el cálculo rápido falla en un paso, Solidon lo calcula a fondo en la misma pasada en lugar de detenerse.
- Un hallazgo que dice que un paso no tuvo efecto abre ese paso en el campo correspondiente.
- Al quitar un cuerpo, el informe deja de hablar de él, y el historial muestra qué pasos ya no dejan nada.
- Un taladro seleccionado ya no vuelve en silencio a su cuerpo tras recalcular. Antes, Supr podía quitar entonces el cuerpo entero.
- Cada función se llama igual en todas partes. La herramienta *Dividir* ofrece *Dividir por un plano*, *Dividir por una línea dibujada* y *Dividir en piezas sueltas*.
- En el cuerpo seleccionado, *Dividir automáticamente …* está ahora en *Preparar*.
- En la ventana en reposo solo *Bloques* destaca en color. El rojo queda para los botones que descartan o borran, y las preguntas se abren con el foco en *Cancelar*.
- En el modo de dibujo, la pestaña *Selección* se oculta. La lista de restricciones muestra las de los puntos y líneas seleccionados, además de cualquier conflicto.
- En la tarjeta de parámetros, una medida solo muestra «Sin utilizar» cuando es así. El botón dice cuántos números fijos se pueden vincular a medidas.
- El informe de errores adjunta un registro de fallo solo cuando Solidon se ha cerrado de verdad por un fallo.
- La tarjeta del recorrido es tan alta como sus pasos. Un paso se despliega con un clic o la barra espaciadora, y ninguna burbuja tapa ya la vista.
- Si un paso del recorrido señala el informe de comprobación, el recorrido sigue a la vista. La pestaña queda enmarcada y el paso dice cuál abrir.
- Un clic en la i junto a una acción de la pestaña *Selección* abre el manual donde se explica esa acción.
- Cada cota de un bloque se puede vincular con fx a una cota del proyecto, aunque todavía no tenga ninguna expresión.
- Tras arrastrar el tirador de una vista previa, ya no queda ningún número sobre la vista. Un número tecleado al arrastrar mueve la vista previa, no el cuerpo elegido.
- Tras *Reparar y volver a intentarlo* y caminos parecidos, el historial ya no llama «eliminado» a un paso que sigue calculando. Si la cadena vuelve a parar, el paso queda marcado.
- El botón *Filamentos* está ahora en la cabecera. Muestra los filamentos del proyecto y lleva al inventario de filamentos.
- Otro filamento se ve al instante, también en bloques y cuerpos STEP, y Solidon no recalcula nada por ello. Los cuerpos seleccionados muestran su color de filamento bajo el resaltado.
- En la pestaña *Selección*, el campo de filamento solo asigna con un clic o Intro. Las flechas y la escritura solo recorren la lista, y la rueda del ratón desplaza la pestaña.
- En las versiones traducidas, *Filamento nuevo* ya no se desplaza de lado cuando la ventana es más baja que su contenido.
- Los modelos grandes se cargan notablemente más rápido y necesitan menos memoria, también con un historial largo y en equipos con 8 GB.
- Incluso en un historial largo, un paso nuevo apenas tarda más en calcularse que el primero.
- Deshacer y rehacer son más rápidos, y la memoria que ya no se necesita se libera enseguida.
- Reparar y resolver solapamientos es hasta cuatro veces más rápido en modelos grandes, y exportar a 3MF, bastante más rápido.
- El área de trabajo aparece más rápido al abrir archivos 3MF grandes.
- Un modelo añadido queda después a la vista, aunque se coloque junto a otro sobre el que se había hecho zoom.
- En el catálogo de bloques, *Gestionar bloques* aparece abierto mientras aún no haya ningún bloque propio.

### Imprimir y entregar al slicer

- En Linux, Solidon crea ahora el archivo de impresión también con Cura como Flatpak o AppImage.
- En Linux, las impresoras de OrcaSlicer, Bambu Studio, ElegooSlicer y Creality Print como AppImage se ofrecen de inmediato, aunque el slicer nunca se haya abierto.
- El diálogo de impresión ofrece las impresoras del slicer elegido, como *Primeros pasos* y *Ajustes*. Una impresora adoptada así se queda con su slicer.
- En el diálogo de impresión se puede cambiar el slicer como en *Primeros pasos*, también con *Elegir programa …* para uno que Solidon no encuentra por sí mismo.
- Una impresora de la lista de Solidon y la misma del slicer cuentan como un solo equipo. El diálogo elige el perfil con la boquilla correcta y el archivo lleva el código de inicio.
- Sin un perfil del slicer guardado, la exportación y la ventana principal usan lo que el diálogo de impresión propone para la impresora, con la máquina y el proceso del fabricante.
- Solo se ofrecen los slicers con los que trabaja Solidon, además de slicers de resina como ChituBox y Lychee. Bambu Studio como AppImage ahora también cuenta.
- El código de inicio y el volumen de impresión vienen solo de su impresora, no de otro modelo de la misma serie.
- El diálogo de impresión asigna los perfiles del slicer mucho más rápido, al abrirse y tras cada cambio de slicer.
- La exportación 3MF solo vuelve a leer los perfiles del slicer si algo cambió allí, y es bastante más rápida.
- El tiempo de impresión estimado se acerca más al del slicer, mucho más en piezas con soportes.
- La comprobación de si los soportes y el skirt caben en la cama mide ahora solo bajo los voladizos. Las piezas cerca del borde ya no reciben un aviso sin motivo.
- Las sugerencias aceptadas ya casi no dejan sin soporte voladizos que lo necesitan. *Mantener libres los canales* solo bloquea el espacio del que ya no se podría sacar un soporte.
- Donde los soportes bajo voladizos pequeños se apoyan en el modelo, Solidon sugiere soportes en árbol. Allí dejan menos marcas.
- En puntas pequeñas, Solidon sugiere una *Velocidad mínima al frenar* más baja para que no se ablanden. El ajuste llega a cualquier slicer.
- Los bordes estrechos que se sostienen solos quedan libres con *Bordes sin soporte*. Así la impresión necesita bastante menos soporte.
- Los soportes se quitan con más facilidad: el espacio sigue el material y la altura de capa de cada pieza, también con varios materiales en una placa. La separación sigue la superficie de encima.
- Si un soporte se apoya en la pieza, Solidon sugiere también una capa de separación debajo para que su pie no deje marcas. Con soportes en árbol, solo en los slicers que la imprimen ahí.
- Con soportes en árbol y junto a una torre de purga, Solidon propone el espacio del soporte en capas enteras, tal como lo imprime el slicer.
- Bajo una cara inferior grande y plana, Solidon propone cuadrícula en lugar de árboles, e híbrido si también hay detalles finos. Para soportes de árbol altos, Solidon propone dos paredes.
- Si una sugerencia del diálogo de impresión solo vale para algunas piezas, la fila y el campo nombran también las piezas que reciben con ella otro valor.
- Con Cura y soportes de rejilla, el espacio del soporte sigue al material: exacto arriba, en capas enteras abajo. Donde Cura redondea hacia arriba, el campo indica el valor impreso.
- Bajo los soportes de árbol de Cura, Solidon propone una capa de separación superior, porque sin ella Cura deja una capa más de aire.
- Para PLA, Solidon propone más espacio entre muchas puntas finas y los soportes en árbol situados debajo. Así quedan menos restos de las puntas de los soportes.
- Si muchos voladizos pequeños necesitan soportes juntos, como una barbilla con la cara inferior inclinada, el informe indica ahora el lugar.
- Un borde estrecho que se sostiene solo ya no cuenta como puente largo, tampoco junto a otro voladizo. El informe ya no avisa ahí, y Solidon no pide soportes por ello.
- Sobre un canal, el informe ya no aconseja un soporte que luego no se podría sacar. Nombra el canal y una transición de menos de 45 grados.
- Para PETG, Solidon sugiere refrigeración total en el soporte. Así se suelta más fácil de la pieza.
- Nuevo en los ajustes de impresión: *Capas de separación inferiores*, *Hueco en la capa de separación* y *Refrigeración total en el soporte*.
- El campo *Espacio superior* se llama ahora *Espacio arriba y abajo* y vale para ambos lados del soporte.
- Si el slicer rechaza filamentos con temperaturas demasiado distintas en una placa, Solidon indica ahora el motivo y qué hacer, en lugar de decir solo que no se creó ningún archivo.
- En el diálogo de impresión, impresora, filamentos y calidad se ven enteros también con la letra ampliada. Las etiquetas largas pasan a la línea siguiente.
- El informe de comprobación calcula más rápido y necesita menos memoria.
- En Linux con Flatpak, Solidon indica ahora que el slicer se ha bloqueado, en lugar de decir solo que no se creó ningún archivo.
- Incluso con el ordenador a plena carga, Solidon indica el motivo real al detener un slicer, en lugar de un tiempo agotado. Un archivo de impresión terminado se aprovecha.

### Roscas, taladros y piezas normalizadas

- Las roscas admiten ahora cualquier diámetro hasta 1000 mm, ya sea con *Rosca imprimible*, en un taladro, con *Crear tornillo* o *Generar tapa roscada*.
- Los taladros normales también se pueden crear y volver a tapar con diámetros de hasta 1000 mm. Los taladros grandes y los avellanados mantienen su forma redonda.
- Tornillos, tuercas y arandelas están disponibles según ISO de M1,6 a M64. Para otros tamaños, *Medida propia* deriva las medidas de los tamaños vecinos y lo indica.
- Con *Ajustado al taladro*, *Pasador para taladro* construye la contrapieza: una cabeza avellanada enrasada para un avellanado, una rosca exterior del mismo tamaño y paso para una interior.
- En una rosca interior impresa, la selección ofrece directamente *Pasador para taladro*.
- Si en un taladro hay una pieza separada, como un pasador, las acciones del taladro lo dicen y ofrecen *Dividir en piezas sueltas*. Antes, el pasador se fundía en silencio con la placa.
- Nuevo: el *Perno roscado*, una varilla roscada o espárrago sin cabeza, con chaflán en ambos extremos y la misma rosca imprimible que el tornillo y la tuerca.
- También en taladros de bloques como el agujero para tornillo, el inserto termofijado o el alojamiento de tuerca, *Pasador para taladro* crea el pasador adecuado, y avisa si no están en el cuerpo.
- Colocado a mano sobre una cara, el alojamiento de tuerca corta su hueco en el material. Hasta ahora el hueco quedaba encima y solo se taladraba el agujero para tornillo.
- El agujero para tornillo del alojamiento de tuerca atraviesa exactamente la pieza, también una gruesa. Hasta ahora terminaba 10 mm bajo el hueco o perforaba el lado opuesto de una ranura.
- Colocado desde abajo, el alojamiento de tuerca tiene el hueco bajo la cara y su ranura baja hasta él. Hasta ahora el hueco quedaba medio encima, con el tornillo en la cara.
- Si el taladro de un bloque no atraviesa la pieza, ahora se llama ciego. Hasta ahora se llamaba pasante.
- Si la pared es más gruesa de lo indicado en *Pasacables* o *Espiga para manguera*, el paso lo dice y abre el espesor de pared. Hasta ahora el paso acababa en el material sin aviso.
- Si hay una pieza separada en un avellanado, una ranura, una cuenca, una garganta o una rosca, las acciones lo dicen. Hasta ahora se cortaba o se fundía.

### Bloques

- Los bloques que son una pieza por sí solos, como clips para cable, nervaduras o tuercas, se crean sin selección como cuerpo propio en un sitio libre de la placa, también en un proyecto vacío.
- Sus propios bloques también se crean así como cuerpo propio y no se unen a un cuerpo que ya está en el proyecto.
- Con *Guardar la selección como bloque* se guarda el cuerpo seleccionado con exactamente los pasos que lo construyen. Si viniera un segundo cuerpo, el diálogo lo indica antes.
- Soportes de pared, abrazaderas de tubo y de perfil y soportes admiten cualquier tornillo de M3 a M64. Si un tamaño no encaja con las demás medidas, el bloque indica qué cambiar.

### Editar y dibujar

- Con *Mover característica*, el material de la característica viaja tal como está y el sitio anterior se rellena limpiamente. Donde no es posible, la selección lo dice de entrada.
- En cordones y gargantas, la selección solo ofrece lo que la operación puede hacer de verdad.
- Si junto a una pared hay un redondeo, *Aplicar ángulo de desmoldeo* avisa antes de calcular de que estorba y propone *Quitar característica* como salida.
- Al recortar una parte de un cuerpo, desaparecen también los chaflanes, roscas y alojamientos de tuerca de los bloques que había en ella.
- En *Generar tapa* y *Generar tapa roscada*, un campo vacío para la altura de la abertura significa «Borde superior», y 0 es la altura de la cama. Los proyectos antiguos conservan su abertura.
- Un boceto se resuelve igual en cualquier ordenador y posición, también al arrastrar, y una restricción de ángulo ya no voltea las líneas. Los proyectos anteriores se calculan como se guardaron.
- Un boceto con muchas formas separadas se resuelve rápido, incluso con cientos de rectángulos o círculos acotados.
- Si *Curvatura continua* no puede cumplirse al dibujar, el editor de bocetos lo indica en segundos y no en minutos.
- Si dos restricciones se contradicen, el editor de bocetos nombra ambas en lugar de reducir una línea o un círculo a un punto.
- Un cuerpo se levanta con tres clics: *Dibujar* en la barra superior (Ctrl+Mayús+E), luego esquina, esquina opuesta, altura. Hacia fuera se une, hacia dentro recorta.
- Al levantar se pueden escribir las medidas. Un doble clic en el paso abre sus medidas, y en *Tipo* se convierte en un sólido de revolución o un patrón de orificios sin volver a dibujar.
- Desde el editor de bocetos, *Terminado* vuelve a la vista y el siguiente clic pone la altura. Escape aparta el contorno, Ctrl+Z lo recupera.
- Si un paso nuevo no se puede calcular, el borrador sigue en la vista y *Reparar y volver a intentarlo* lo calcula sin otro clic.
- Para modelar hay cuatro herramientas, cada una con su botón y su atajo. La intensidad es un nivel de 1 a 10, y repasar la misma zona ya no acumula material.
- El pincel se ajusta al tamaño del cuerpo. Si la malla es demasiado gruesa, *Modelar* iguala los triángulos en el primer trazo, y un Ctrl+Z deshace ambas cosas.
- Al reflejar, el plano queda donde el cuerpo coincide consigo mismo, aunque una parte sobresalga mucho hacia un lado.
- Modelar sigue al ratón con fluidez, y hasta un paso con cientos de trazos de pincel se calcula rápido.
- En *Esqueleto*, cada clic después del primero pone un hueso, Intro termina la cadena, arrastrar una articulación la dobla y *Terminado* lo guarda todo sin diálogo.
- Un esqueleto solo dobla lo que cuelga de sus huesos, y el resto del cuerpo se queda quieto. Los proyectos anteriores se calculan como se guardaron.
- Con Ctrl o Mayús selecciona varias aristas y las redondea o achaflana en un solo paso. Un clic en una esquina selecciona todas las aristas que se juntan allí.
- En un cuerpo exacto, el resaltado de una arista muestra también las aristas tangentes contiguas que *Redondear* y *Aplicar un chaflán* incluyen.
- Lo que la selección ofrece en una característica, la operación lo ejecuta con esos mismos valores. Lo que aparece en gris lo dice con la misma frase, también por chat y línea de comandos.
- Como lugar de la copia, *Duplicar característica* propone una anchura y media junto al original, con una pared entre ambas y nunca a lo largo de su eje.
- En un avellanado, *Girar característica* propone el mayor ángulo con el que sigue siéndolo, y avisa cuando un giro solo deja la característica sobre sí misma.
- Si una acción alcanzara una pieza separada junto a la característica, o una característica colocada tocara otro material solo en una línea, Solidon lo dice en vez de dañar el cuerpo.

### Generar con IA

- El diálogo de generación calcula en local con TRELLIS.2 y FLUX.2 [klein] en lugar de TripoSG y SDXL. Un texto se convierte primero en imagen y la imagen, en el modelo.
- Antes de descargar, la configuración indica licencias y tamaños de los modelos. Quita la antigua configuración de TripoSG de Solidon y dice antes qué carpetas son y cuánto ocupan.
- Las paredes finas, por ejemplo de un jarrón, llegan cerradas y con grosor.
- El asistente responde en el idioma en que usted escribe.
- Con un modelo local, el asistente tiene tanto margen como con uno alojado y completa encargos de hasta doce pasos.
- Los modelos generados llegan cerrados más a menudo. Donde las caras solo se tocan, Solidon las separa, y alisa pequeños pliegues de la superficie en vez de avisar de una autointersección.
- Si un intento ya se deshizo al generarse, el diálogo lo dice antes de aceptarlo y ofrece *Otro intento*.
- Si un modelo generado es solo una piel fina alrededor de un hueco, lo dice el diálogo antes de aceptarlo y el informe de comprobación después, con el camino a un nuevo intento.
- Antes de descargar, *Configurar el chat* y *Configurar ComfyUI* indican cuánta memoria gráfica y espacio necesita un modelo y si este equipo los tiene.
- En un Mac, *Configurar el chat* propone un modelo local que cabe en la memoria compartida y dice cuándo conviene más una clave para un modelo alojado.

## 0.5.3

### Manejo y sistema

- A la derecha hay una tarjeta con las pestañas *Selección*, *Informe de comprobación* y *Chat*. Los avisos nuevos ya no traen el informe al frente; su pestaña los indica con un símbolo y un número.
- Arriba en la ventana, *Buscar función* (Ctrl+Mayús+P) encuentra cualquier función. El mapa de funciones sigue el orden de la barra de menús.
- En la selección, cada característica tiene una sola acción abierta a la vez. Las demás quedan plegadas y muestran sus valores.
- Los diálogos de operación muestran delante como mucho cuatro campos y una frase. Lo que rara vez se cambia está en *Más ajustes*, los límites en *¿Cuándo evitarla?*.
- Un cero con significado dice en el campo lo que hace, por ejemplo «automático», «sin» o «del material».
- Todos los diálogos tienen la misma forma, con secciones planas y un borde común para las etiquetas, también los ajustes, el diálogo de IA y la activación.
- El informe de comprobación muestra primero los hallazgos, con una línea de estado y contadores encima. *Exportar …* está junto a *Entregar al slicer …*.
- Hallazgos, pasos del recorrido y avisos son más cortos. Donde un botón ofrece la acción, la frase ya no la repite.
- La acción *Reconstruir modelo* está en el cuerpo seleccionado.
- La pantalla de inicio muestra arriba, en grande, las cuatro formas de empezar. *Primeros pasos* pregunta idioma, slicer e impresora y pliega el resto.
- El catálogo de bloques muestra imagen y título en cada ficha. En un taladro, *Bloques adecuados …* muestra solo lo que va en un taladro.
- El diálogo *Guardar la selección como bloque* muestra una fila por medida con su valor por defecto y sus límites.
- En Windows, el puntero propio de Solidon vuelve a hacer clic justo en su punta. Hasta ahora el clic caía unos píxeles al lado.
- La búsqueda en el manual ya no se interrumpe con un error cuando un carácter más deja de encontrar resultados.
- Si deshace o borra un paso mientras *Editar este paso* está abierto, el diálogo se cierra y lo indica.
- Se ha corregido un bloqueo poco frecuente de la aplicación durante la comprobación de impresión.
- En el Mac, las frases que nombran un atajo usan las teclas del Mac, es decir ⌘, ⇧ y ⌥.
- En el Mac, la tecla de borrar elimina cuerpos, características, pasos del historial y líneas de un dibujo.
- En Linux, el atajo de rehacer que nombran el recorrido y las indicaciones también recupera un paso.

### Imprimir y entregar al slicer

- Se añade Anycubic Slicer Next, con las 39 impresoras de Anycubic, en Windows, macOS y Linux.
- En Linux, Solidon encuentra OrcaSlicer, Bambu Studio y PrusaSlicer instalados como Flatpak, con sus impresoras y perfiles, también desde el propio Flatpak de Solidon.
- En Linux, los slicers en AppImage también ofrecen las impresoras de fabricante que tenga configuradas en ellos.
- En el Mac, Solidon ahora también genera el archivo de impresión con Cura. Hasta ahora solo encontraba la ventana de Cura.
- Creality Print 7 aporta sus propias impresoras y la última que eligió.
- Las listas de impresoras nombran cada impresora una sola vez, sin variantes de boquilla. La boquilla se elige en los ajustes de impresión.
- La boquilla elegida en los ajustes de impresión se mantiene aunque después guarde los ajustes del programa.
- Si cambia la boquilla para PrusaSlicer o SuperSlicer, el slicer recibe también el perfil de impresora que corresponde.
- Solidon ofrece más impresoras, también aquellas cuyo perfil no indica placa ni boquilla, como la Creality CR-20 y la Anycubic i3 Mega en PrusaSlicer.
- Los ajustes de impresión muestran delante slicer, impresora, boquilla, filamentos, calidad, densidad de relleno y soportes; el resto está en *Más ajustes*.
- Cada motivo de una sugerencia en los ajustes de impresión cabe en una línea. *Guardar archivo de impresión* aparece en cuanto hay un archivo de impresión.
- Las piezas más anchas arriba que en la base ya no reciben un aviso de borde si el brim y el skirt quedan sobre la placa.
- Los soportes aceptados llegan también bajo los puentes con capas finas. Hasta ahora *Mantener libres los canales* podía quitarlos allí por completo.
- Si los soportes están activados y no llega ninguno al slicer, Solidon lo dice después de laminar y nombra la salida.
- OrcaSlicer y ElegooSlicer generan el archivo de impresión aunque un perfil del fabricante contenga valores que ellos mismos rechazan. Solidon nombra cada valor sustituido.
- Si un perfil da una punta de soporte en árbol más estrecha que la línea de soporte, Solidon la ensancha para que el slicer calcule con soportes.
- Si un slicer aplica un ajuste de otra forma, el aviso nombra el campo y ambos valores y lleva a los ajustes de impresión.
- En Linux, Solidon ofrece también PrusaSlicer y OrcaSlicer del gestor de paquetes junto con sus impresoras del fabricante.
- En un Mac cuyo sistema de archivos distingue mayúsculas y minúsculas, Solidon encuentra las impresoras del fabricante dentro del paquete del slicer.

### Taladros, ranuras y división

- Una rosca o un inserto termofijado en un taladro seleccionado ya no se detiene con «fuera de la superficie». Si el taladro es demasiado ancho, Solidon indica tamaños adecuados.
- En un taladro seleccionado, la vista muestra solo diámetro, profundidad y dos cotas a aristas. Las referencias se nombran por su lado, por ejemplo «Arista exterior izquierda».
- En pulgadas, la frase sobre un taladro da su medida en pulgadas.
- La franja de vista previa dice en una línea qué cambia, con las longitudes en su unidad de visualización.

### Modelar, texto y dibujo

- En soportes y placas con taladros, avellanados y texto, *Reconstruir modelo* crea ahora un contorno con alojamientos restados. Si no encuentra una estructura, lo dice.
- Si al dibujar toma la sección de un cuerpo convertido, sus círculos y arcos llegan como círculos y arcos.
- Si una pieza no se puede convertir en caras y aristas, Solidon indica el motivo y una salida en lugar de terminar con un error inesperado.

### Generar con IA

- El aviso de IA explica en dos frases por destino qué se envía. Como el texto ha cambiado, tendrá que confirmarlo una vez más.
- Las descripciones de los modelos locales recomendados son más cortas.

## 0.5.2

### Formas y bloques nuevos

- Nueva es la forma básica «Añadir un tubo»: diámetro exterior y altura, y además espesor de pared o diámetro interior, en un solo paso.
- Nuevo es el bloque «Pestaña con agujero»: una pestaña plana en cualquier cara, con agujero y medidas según el tornillo de M3 a M8.
- Nueva es la «Abrazadera de tubo» para tubos habituales de 15 a 40 mm o cualquier medida propia hasta 110 mm, con tornillo de apriete M3 a M6 y la holgura de su material.
- Nuevo asistente «Recipiente con tapa»: redondo o rectangular, tapa de rosca, a presión o abatible, y si quiere compartimentos, inserto y agujeros de espolvoreo. Sus cotas principales son parámetros.
- Cuatro soportes se crean en un paso con caras y aristas reales: en U, redondo, de horquilla y con repisa, fijados con ojo de cerradura, agujeros para tornillos, gancho de panel o pinza.
- Nuevos son «Cierre de bayoneta» y «Disco giratorio con retención», cada uno como par a juego, y «Manguito de inserción y conector de varillas» para dos a cuatro varillas.
- Nuevos son «Espiga para manguera», cuyo paso atraviesa la pared, «Unión de canal» para canaletas, y «Suelo de habitación», «Pared de habitación» y «Cristal de ventana» para habitaciones encajables.
- Una escena vacía muestra cómo empezar: caja, cilindro, dibujo, bloques o un archivo que arrastre dentro.
- Los cuerpos nuevos aparecen sobre la placa, no en un cuerpo seleccionado, y quedan seleccionados. En una cara seleccionada se colocan donde hace clic o centrados y, si quiere, ya unidos a la pieza.
- Bloques como un bolsillo para imán o un orificio para tornillo quedan donde hace clic en la cara. Su distancia a dos aristas se mantiene si la pieza cambia después.
- La «Lengüeta para perfil de aluminio» encaja en Motedis 20 × 20 tipo B ranura 6 y 30 × 30 tipo B ranura 8, con cabeza a la forma de la ranura. Los tres tamaños previos quedan como medidas antiguas.
- En el informe, «Reconstruir modelo» rehace una pieza importada, también escuadras, gargantas y avellanados, la compara con el original dentro del límite elegido y la aplica en un solo paso.
- La «Abrazadera con revestimientos» empieza con el material del proyecto en los dos campos de material. Hasta ahora ambos estaban vacíos.
- La búsqueda de piezas encuentra la «Lengüeta para perfil de aluminio» también como tuerca en T, y su descripción dice en qué se diferencia de una tuerca en T con rosca.
- Una tapa de «Generar tapa» puede llevar bisagra, impresa en su sitio o con un pasador de «Pasador para taladro», y su collar queda recortado para abrirse sin tropezar.
- Con «Rebajar contraforma», un inserto recibe alojamientos para herramientas que vuelven a salir en línea recta.

### Imprimir y entregar al slicer

- Se puede cancelar la preparación de la exportación 3MF. En trabajos con varias placas, Solidon reutiliza las capas y sugerencias ya calculadas.
- Los filamentos sin uso de proyectos antiguos ya no se envían al slicer. Los perfiles siguen asociados a los filamentos utilizados.
- Los modelos añadidos encuentran espacio también después de la duodécima placa. Las placas importadas conservan su distribución.
- Los modelos añadidos con filamentos distintos van en placas separadas si la impresora no tiene suficientes boquillas.
- Al cambiar de impresora o de slicer, la placa de impresión seleccionada antes ya no se transfiere al nuevo perfil.
- Las piezas esbeltas se colocan más cerca del centro. Puede ajustar la separación del borde; para bases pequeñas se propone un borde en contacto con la pieza.
- Se avisa de los perfiles dañados en PrusaSlicer y SuperSlicer. Solidon utiliza entonces su conjunto completo de ajustes de impresión.
- Los ajustes de cada pieza llegan al slicer con más fiabilidad. Los que afectan a toda la placa se explican en la pieza correspondiente.
- Si acepta un brim solo para una pieza esbelta, las demás piezas conservan su propia elección de adherencia, y el campo nombra las piezas a las que se aplica el brim.
- Con Orca y Prusa, aceptar una sugerencia de velocidad para un encaje solo ralentiza las piezas afectadas.
- También se conservan al exportar los pequeños cambios aceptados en los ajustes de impresión.
- Cura usa los límites de cambio brusco de velocidad del perfil, con valores separados para paredes, relleno y primera capa.
- Si Cura tiene otra impresora seleccionada, el envío indica ambas y muestra dónde adoptar la selección de Cura.
- Corregido un cierre inesperado de ElegooSlicer y OrcaSlicer al laminar modelos multicolor con soportes de rejilla.
- Tras laminar, Solidon también compara el material de soporte y las capas del modelo por placa. El informe muestra la estimación interna y los valores del archivo de impresión.
- La comparación de material considera solo el modelo impreso. La purga se muestra por separado y se indica si su cantidad no puede leerse por completo.
- La comparación del tiempo de impresión cuenta desde la primera capa con las velocidades de su impresora, también con soportes, y ya no avisa de una gran desviación en casi cada impresión.
- El análisis de capas es varias veces más rápido en modelos huecos y en modelos con muchos techos, y conserva los contornos finos. La vista de capas aprovecha lo que el informe ya calculó.
- En piezas superpuestas, el análisis de impresión ya no cuenta el aire encerrado como material. También mejora la detección de voladizos y soportes necesarios.
- En el primer inicio y en los ajustes elige primero el slicer y después una de sus impresoras. La lista tiene un campo de búsqueda, y el volumen y la boquilla vienen del perfil del slicer.
- Si en el primer inicio hace clic en «Guardar e iniciar» mientras Solidon aún busca las impresoras del slicer, la aplicación ya no se congela.
- La boquilla se elige en los ajustes de impresión entre los tamaños que conoce su impresora, y el slicer recibe el perfil que le corresponde.
- Los ajustes de impresión preguntan en el orden en que una cosa depende de otra: slicer, impresora, boquilla, placa, filamentos y calidad, y después los valores.
- Ahora puede generar archivos de impresión directamente desde Solidon con Creality Print 7.2 y 7.3.
- Con Cura, Solidon adopta si usted lo pide la impresora que Cura está usando, con su propia boquilla. Una impresora renombrada en Cura se vuelve a reconocer.
- Cura lamina ahora con la boquilla que usted eligió, también en impresoras de la lista de Cura, y las impresoras con el origen en el centro de la placa lo conservan.
- Las impresoras con el origen fuera de la esquina de la placa, como delta, BIBO o Dremel, reciben las piezas donde Solidon las pone. Antes quedaban en el borde o el slicer las reorganizaba.
- Bambu Studio recibe la variante de boquilla y las temperaturas de sus bobinas, hasta el archivo 3MF.
- Si elige brim, skirt, raft o «Automático» en los ajustes de impresión, solo aparecen las medidas que recibe su slicer, sin campos que no harían nada.
- Un número fuera de su límite se queda en el campo, el límite aparece al lado y «Laminar» espera hasta que sea correcto. Hasta ahora se recortaba sin aviso.
- Las piezas altas y delgadas sobre una base pequeña reciben la sugerencia de paredes más tranquilas, a 60 mm/s y con menos aceleración. En la Centauri Carbon 2 esas varillas se arrancaban.
- Con Cura, el informe de comprobación nombra las piezas que solo reciben esos valores de rebote, porque Cura los acepta solo para toda la placa.
- Solidon sugiere «Pared exterior primero» solo para la pieza que lo necesita y nunca para una con soportes.
- La búsqueda rápida de «Orientar para imprimir» también comprueba si una pieza se sostiene con seguridad. Si una no se sostiene en ninguna parte, orienta igual las demás y el informe la nombra.
- Con «Organizar sobre la placa», cada pieza va a la primera placa donde cabe. El juego de minigolf necesita así cuatro placas en lugar de seis.
- Si arrastra un cuerpo en la vista a otra placa, pasa a pertenecer a esa placa.
- Cuando llega otro modelo, desde un archivo, una descarga o generado, la vista muestra la placa en la que está.
- Otro modelo se coloca en el hueco libre más cercano al centro de la placa, en lugar de la esquina trasera izquierda.
- Tras el primer «Abrir en el slicer …», Solidon ya no vuelve a calcular el historial.
- La comprobación cruzada con SuperSlicer ya no informa de un código de inicio omitido cuando no se omitió ninguno.
- SuperSlicer ya no se bloquea con piezas redondas: ya no recibe la costura en bisel que no conoce.
- SuperSlicer recibe soportes de rejilla con un aviso si se eligieron soportes de árbol. La costura más cercana se aplica sin avisos falsos.
- TPU selecciona el perfil de filamento y sus valores de inicio en PrusaSlicer y SuperSlicer. Si falta un perfil, Solidon indica que usa su propia tabla de materiales.
- Cura respeta los límites de aceleración e informa de los valores propios reducidos. El relleno sólido usa la velocidad de relleno; solo la cara superior usa la velocidad de superficie.
- Cura toma la velocidad mínima del ventilador y el umbral de tiempo de capa del perfil de su impresora. Hasta ahora el ventilador se encendía ya en la primera capa, donde debía estar parado.
- La temperatura de cámara llega al campo correcto del slicer. Los perfiles sin calefacción de cámara regulable explican por qué el valor no tiene efecto.
- El relleno Líneas llega a Bambu Studio y Creality Print como líneas, sin sustituirse por Rejilla o Cúbico.
- Tras cortar, Solidon avisa de ajustes descartados por PrusaSlicer o los slicers de Orca. También detecta cambios en el borde, el orden de paredes y el tipo de soporte.
- La preselección de filamento toma Generic o la marca de su impresora en lugar de un filamento especial ajeno, por ejemplo Generic PETG en vez de BETA PETG en la Bambu A1.
- Ahora «Orientar para imprimir», «Girar» y «Trasladar» funcionan también con modelos de superficies STEP, con giros de casi 180° y en caras reconocidas en parte. El cuerpo sigue exacto.
- Una pared exterior más lenta se aplica ahora también a perímetros pequeños como agujeros y tallos en PrusaSlicer y la familia Orca.
- PrusaSlicer y la familia Orca respetan la densidad de soporte elegida. El campo empieza en 1 %. Para imprimir sin soportes, elija «Ninguno».
- En impresiones multicolor con OrcaSlicer, ElegooSlicer, Bambu Studio y Creality Print, la torre de purga recibe una posición inicial adaptada al tamaño de la placa.
- Las piezas demasiado grandes se indican antes de iniciar el slicer. Si no se encuentra sitio para todas en una placa, puede distribuirlas en varias placas.
- Los caracteres especiales en nombres de proyecto o usuario ya no impiden generar el archivo de impresión. Cura también lee modelos con nombres turcos o chinos.
- Solidon coloca las piezas superpuestas en la base antes de laminarlas con PrusaSlicer o Cura y avisa si no encuentra una disposición adecuada.
- Si PrusaSlicer o SuperSlicer indica que la primera capa está vacía, Solidon identifica la pieza y permite colocarla en la placa o abrir los ajustes de impresión correspondientes.
- Las advertencias de PrusaSlicer y SuperSlicer aparecen en el informe aunque el slicer termine bien, una capa vacía como error. La separación del raft se ajusta aparte.
- Si el slicer reparte una placa en varios archivos de impresión, Solidon lo indica y ofrece reorganizar o exportar. Antes tomaba en silencio solo uno de ellos.
- Arriba en el informe se ve si la transferencia está lista, requiere una decisión o no se recomienda, y qué falta por comprobar. Sin avisos, una pieza ya no cuenta por sí sola como lista para imprimir.
- Un aviso seleccionado indica su consecuencia para la impresión, y cada acción ofrecida dice qué más cambia.
- Tras exportar o «Abrir en el slicer …», Solidon vuelve a leer el archivo. El registro del informe indica archivos, destino de impresión, material, ajustes y si el archivo coincide con el encargo.
- Exportado como 3MF desde la línea de comandos, un cuerpo de un solo color conserva su filamento al volver a abrirlo.
- Para los ajustes de piezas concretas, la línea de comandos indica qué piezas son y qué valor reciben.
- Si acepta soportes para un puente largo sobre la propia pieza, ahora llegan también ahí. Antes se añadía «Solo desde la placa», y varios slicers imprimían el puente sin soporte.
- Las piezas pequeñas tumbadas, como tornillos, ya no reciben soportes propuestos donde un borde de corte mostraba por error un punto flotante.
- Si una pieza termina arriba en una arista que el slicer no imprime, Solidon ya no avisa tras el laminado de un modelo cortado.
- Si la primera capa de una pieza es más estrecha que una línea, el aviso tras el laminado propone las líneas de pared y la balsa como salida.
- SuperSlicer conserva la disposición de Solidon y ya no empuja las piezas hasta el borde de la placa; la falda queda sobre la placa.
- Si una pieza solo cabe girada en la placa, llega girada a OrcaSlicer, Bambu Studio y ElegooSlicer; si a Creality Print no le basta el margen, Solidon lo dice antes.
- Solidon solo propone un borde de adherencia tan ancho como permite la placa.
- Si el borde alrededor de una pieza entra en una zona prohibida de la placa, la comprobación antes de exportar lo dice.
- Si en el slicer se cruzan las trayectorias de dos piezas, o de una pieza y la torre de purga, el aviso lo dice y ofrece salidas.
- Si el borde de adherencia está en automático, Solidon avisa antes de exportar cuando puede crecer fuera de la placa o en una zona prohibida, y propone un ancho fijo.
- Los soportes y la falda junto al borde de la placa cuentan en la comprobación antes de exportar, con el ensanche de la primera capa de soporte que indica el perfil del slicer.
- Los archivos STL exportados desde piezas STEP no contienen triángulos sin superficie.

### Taladros, ranuras y división

- El ángulo de una ranura en un taladro importado apunta en la dirección esperada y se mantiene al cambiar la finura.
- Una ranura en una pared lateral orientada a la izquierda o a la derecha se puede acortar, estrechar y girar. Los proyectos de versiones anteriores conservan sus ranuras hasta que cambie el paso.
- En cuerpos STEP, una ranura en una cara inclinada ya no cuenta como sobresaliente por el lado, y un segundo arrastre en una ranura que llega a un escalón ya no rellena el cuerpo.
- Una ranura a través de una chapa inclinada o achaflanada muestra toda su profundidad en cuerpos STEP, y su copia más allá del borde da el mismo aviso en piezas STL y STEP.
- En un cuerpo con caras y aristas reales, un bloque colocado después de un taladro queda en la cara elegida, y «Generar tapa roscada» funciona también en el borde de un recipiente vaciado.
- Dos placas que se tocan siguen siendo un cuerpo en un taladro y conservan su material, al estirarlo, cambiarlo, desplazarlo o cerrarlo. Un pasador encima se queda en su sitio.
- Estirar un taladro que atraviesa dos cuerpos ya no informa de que el cuerpo se rompe cuando no ocurre.
- Si un taladro corta el cuerpo en dos, el informe lo dice una sola vez, con el número de piezas al final, y calla en cuanto el cuerpo vuelve a ser una pieza.
- Los patrones sobre caras cilíndricas de modelos importados siguen cerrados al modificarlos.
- En el historial de un cuerpo STEP se pueden reordenar pasos o insertar uno antes, aunque un paso posterior se refiera a un taladro. La referencia sigue al taladro.
- Un taladro simple o una ranura que se desplaza o duplica con una dirección nueva sigue exacto en un cuerpo STEP.
- Una característica reconocida a más de un metro del origen conserva su lugar al cambiarla. Antes el campo recortaba la cifra sin aviso y el taladro se movía.
- Si un paso alcanza una pieza cuya superficie se cruza consigo misma, se detiene y muestra el lugar. Fuera de ella sigue calculando y avisa de que las piezas no se pudieron unir.
- Ahora «Dividir el modelo» corta una figura también por su costura de simetría sin dejarla abierta, y los pasadores ya están en la vista previa.
- Si un corte solo roza una pared, «Dividir el modelo» indica el lugar y lleva a la posición del corte en vez de fallar en los pasadores.
- Recortar corta ahora también en ángulo: arriba elige el «Plano»: en un eje con inclinación, paralelo a una cara, por una arista o por tres puntos que marca en la vista.
- Un cuerpo STEP sigue siendo un cuerpo STEP al recortarlo, con sus caras, aristas y nombres.
- Una tapa roscada recién creada ya no aparece en el informe como demasiado ajustada para su cuello.
- Si un taladro no se puede cortar limpiamente en un cuerpo STEP, Solidon lo hace en el modelo de triángulos en lugar de seguir con un cuerpo dañado.
- Si eligió «Cargar ahora», las piezas de «Dividir el modelo» tampoco inician un reconocimiento de minutos; «Reconocer todas las características» lo recupera.
- Si elige «Dividir el modelo» en una línea de resumen del informe para varios cuerpos, Solidon los divide uno tras otro. Antes solo se dividía el primero.
- Si al «Unir» un cuerpo tapa un taladro del todo o en parte, el informe lo indica con el lugar y el hueco que queda.
- Los patrones circulares y «Reflejar» toman su «Centro de giro» de un cuerpo, una característica, un punto o el origen. El centro queda fijo aunque el cuerpo se mueva después.
- Un arrastre dentro de la abertura de un taladro avellanado seleccionado deja el cuerpo en su sitio, y la línea de estado indica el camino hacia la ranura. Hasta ahora movía el cuerpo entero.
- Si la tarjeta de cotas de un taladro crece en altura, las demás cotas siguen junto al cuerpo, y el tirador para desplazar queda en la boca en vez de dentro de la pieza.
- Si selecciona un taladro hecho en Solidon, su diámetro aparece solo en la tarjeta de cotas de la vista. Hasta ahora aparecía una segunda vez a la derecha.
- Una dirección que introduce a la derecha para una ranura pasa también a la tarjeta de cotas de la vista, y «Aplicar» sigue disponible. Hasta ahora allí volvía a 0°.
- Solidon reconoce conos, también planos y cortos, redondeos y caras estrechas de la misma forma en más modelos, da igual si el modelo está desplazado, girado o escalado.
- Una cara superior abombada se llama también en cuerpos STEP «Cara curva» en lugar de «Redondeo», y las piezas STL redondeadas por completo muestran cada redondeo, como la misma pieza en STEP.
- Las letras y los contornos curvos de modelos importados ya no muestran redondeos falsos.
- Solidon reconoce cada campo de nervios, panal u hoyuelos de un archivo importado como un solo patrón, y «Reconocer características aquí» agrupa las celdas de un campo.
- Un campo pequeño que Solidon solo lee como características sueltas se convierte en un patrón con «Agrupar como patrón». Los patrones de archivos STEP se reconocen directamente.
- Las piezas de una división automática también se numeran en proyectos de versiones anteriores, y un corte eliminado o desactivado ya no cuenta.
- Un taladro que duplica, desplaza o repite a lo largo de una cara inclinada sigue siendo el mismo taladro en piezas STL y STEP, con las mismas medidas y avisos.
- Tras «Repetir característica», una copia en una pieza STEP ya no perfora hasta la cara superior, y un taladro STL de facetas gruesas sigue contando como pasante.
- Una rosca crece o mengua con «Cambiar característica» sin romper la pared, y la rosca contraria de un ajuste roscado cambia con ella.
- Un par de roscas impresas supera su comprobación de ajuste: ambas roscas indican la medida con la que se construyen, y la comprobación espera la holgura de ambas mitades.
- Con «Comprobar la trayectoria de montaje», las piezas también pueden girar, o insertarse primero y luego girar como una bayoneta.
- Para un ajuste, Solidon recorta la misma ventana de ambas piezas como pequeña muestra impresa e indica la holgura.
- Un taladro avellanado que tras duplicar, desplazar o repetir termina por completo dentro del material ya no avisa de que sobresale del borde.
- Si el avellanado de una copia sobrepasa un lado, Solidon vuelve a encontrar la copia igual en piezas STL y STEP.
- Si duplica un taladro a lo largo de su propio eje hacia el vacío, el original conserva su nombre en piezas STL, y la copia se da por perdida como en piezas STEP.
- Una garganta o un cordón que una abertura divide en dos arcos aparece en piezas STEP como un solo anillo en el árbol, igual que en piezas STL y 3MF.
- Las características iguales en piezas STEP, como dos trozos de una superficie cónica, conservan su nombre cuando taladra, duplica, cambia un taladro o inserta una pieza en otro sitio.
- Las características que van juntas aparecen como grupo en el árbol de objetos, y cámaras y cierres cambian en conjunto: medida interior, profundidad, holgura y giro.

### Redondear y achaflanar

- Redondear un grupo de aristas en un cuerpo STEP redondea ahora las aristas posibles en lugar de rechazar todo. «Mostrar el punto» encuentra cada arista omitida.
- Las aristas junto a una pared no más gruesa que el radio quedan vivas, y el informe indica el radio que cabe allí. Antes se rechazaba todo el redondeo.
- Si un cuerpo STEP no tiene arista propia en una zona elegida, el informe ofrece «Finalizar la edición de caras y volver a intentarlo». En el modelo de triángulos se redondea también.
- Si no queda espacio para el intercambio con el proceso de cálculo, Solidon calcula el paso igualmente y lo indica en el informe. Antes se detenía aconsejando calcular más grueso.

### Modelar, texto y dibujo

- Con «En ambas caras», «Aplicar texto» pone las letras también en la cara posterior, legibles desde fuera. Sirve para banderas, carteles y colgantes.
- Los rótulos se componen con más precisión: las letras quedan en su sitio y las curvas siguen la fuente, en vez de perder hasta un 2 por ciento de superficie en tamaños pequeños.
- La simetría al «Modelar» refleja en el centro del cuerpo, también lejos del centro de la placa. Los proyectos antiguos conservan su forma.
- El pincel de modelado actúa solo sobre la cara que tiene delante. Rebajar una placa fina ya no empuja también la cara inferior.
- Un trazo sobre el plano de simetría actúa una vez en lugar de dos, y justo al lado el trazo y su reflejo se funden con suavidad.
- El editor de esqueleto muestra huesos y articulación en la vista, y una articulación queda en el centro del cuerpo en vez de en su piel, así la figura se dobla de forma pareja.
- La barra de modelado llama ahora «Intensidad» al valor del pincel, en lugar de «Espesor», que parecía un grosor de pared.
- Si un trazo de modelado atraviesa la pared o la deja demasiado fina, aparece en el informe y antes de exportar, con «Mostrar el punto» y «Deshacer el trazo».
- Ahora «Fusionar suavemente» calcula fino también en la ventana, mientras el cuerpo no sea muy grande.
- Si un bloque como un ojo de cerradura sobrepasa el borde de su cara, aunque sea solo con el avellanado o el chaflán, o entra en una pared detrás, aparece en el informe.
- Una medida tecleada como longitud 40 estira el dibujo solo en esa dirección. El cuerpo resultante queda cerrado y apoyado en la placa.
- Los dibujos SVG llegan bien: giros, cizallas, esquinas redondeadas, elipses y arcos elípticos son correctos, y las capas ocultas quedan fuera.
- El destino de «Alinear a la característica» empieza vacío, y el primer clic en la vista lo rellena. «Aplicar» espera hasta entonces en vez de poner el cuerpo en el lado equivocado.
- Un archivo en metros que también cabría en la placa leído en pulgadas ya no se lee mal sin aviso. Solidon pregunta la unidad.
- Otro trazo en una cavidad recién excavada la hace más profunda, también con un pincel pequeño. Hasta ahora no surtía efecto y contaba como fallido.
- Al «Modelar», la ventana muestra cada trazo igual de rápido, también tras muchos trazos, y las sesiones grandes calculan su vista previa en segundo plano. Hasta ahora se volvía más lenta con cada uno.
- Con «Fijar el estado», Solidon guarda la sesión de modelado tan fina como la calculan la exportación y la impresión, y la ventana sigue utilizable. Antes guardaba la vista más basta.
- Un doble clic en «Modelar» en el historial vuelve a abrir la sesión con sus trazos. Ctrl+Z deshace un trazo entero, y «Terminado» cambia el mismo paso.
- La entrada «Crear a partir de un boceto …» empieza a dibujar enseguida, el plano de dibujo muestra su origen, y un doble clic en el historial reabre un dibujo en modo de dibujo.
- Al «Modelar» y en el editor de esqueleto, la barra muestra espesor de pared o voladizo como mapa con leyenda y avisa de un trazo fuera del volumen de impresión. Tras doblar, dice cómo se imprimirá.
- Una textura aplicada se selecciona entera. El panel de selección ofrece entonces «Modificar textura» y «Quitar textura».
- El texto sigue un arco o rodea una superficie redondeada, y «Incrustar texto» lo coloca enrasado en su propio color.

### Generar con IA

- Cancelar durante «Otro intento» solo detiene el intento en curso. Los terminados siguen disponibles para elegir.
- Cada intento de la lista indica su frase o su imagen y su semilla. Si su entrada ya no coincide con el intento elegido, el diálogo dice cuál se aplicará.
- Ahora «Configurar modelo de imagen …» descarga el modelo de imagen aunque los demás pesos ya estén.
- Si un error al generar nombra la configuración como salida, aparece como botón en el diálogo.
- Mientras se genera un modelo, la ventana sigue utilizable. El diálogo se aparta, y la barra de estado muestra progreso, tiempo y «Cancelar».
- El diálogo de generar indica el volumen al tamaño con que llega la pieza.
- Un modelo generado se deshace con un solo Ctrl+Z. Antes hacían falta tres o cuatro.
- Si «Aplicar» se rechaza al generar, el diálogo sigue abierto con todos los intentos e indica la salida, en vez de desechar la malla.

### Manejo y sistema

- En el Mac, Solidon ya no se cierra poco después de arrancar. En la versión 0.5.1 ocurría en todos los Mac, incluso sin un ratón 3D conectado.
- La casilla «Crear las medidas como parámetros» viene marcada la primera vez y luego recuerda su última elección, también tras reiniciar.
- Los diálogos se abren al tamaño de su contenido, sin espacio vacío, y un tamaño que usted haya ajustado se mantiene.
- La exportación, «Laminar» y «Abrir en el slicer …» reciben siempre el cálculo fino, no la vista más gruesa de la ventana. Redondeos y conos llegan al archivo con resolución completa.
- Una exportación durante un cálculo en curso espera al resultado nuevo. Antes el archivo podía llevar todavía la medida antigua.
- Si exporta solo una parte de la escena, el diálogo de archivo y la confirmación indican el alcance, por ejemplo «1 de 2 cuerpos».
- La barra de parámetros rechaza una medida fuera de su límite en vez de dejar la vista vacía.
- En la barra de parámetros cuenta cada paso de flecha, y el foco se queda en el campo.
- En la barra de parámetros las medidas de dos cajas llevan su número, y una medida con rango de trabajo propio tiene un deslizador.
- Si un paso espera una pregunta, «Aplicar» sigue disponible y la pregunta aparece.
- En el diálogo de una operación las etiquetas forman una columna, los campos tienen el mismo ancho y cada interruptor está antes de lo que activa.
- Las marcas de las listas se leen en cada fila, y los colores aparecen como un punto redondo al lado.
- La paleta de comandos explica herramientas y acciones de archivo en una frase.
- Tras cambiar el parámetro, «Generar variantes» empieza en el valor de ese parámetro.
- Si falla el guardado de una calibración, se conservan los valores anteriores.
- En el proyecto de ejemplo del segundo camino, los agujeros de los tornillos siguen el ancho y el grosor.
- La ventana «Novedades» y el sitio web muestran el resaltado como texto destacado en vez de asteriscos.
- Todas las traducciones usan las mismas palabras para características, botones y términos de impresión, y los mensajes ponen la puntuación que pide cada idioma.
- El botón que descuenta el consumo del inventario de filamentos se llama ahora «Descontar», y los avisos nombran las acciones como la ventana, por ejemplo «Igualar los triángulos».
- El tratamiento es uniforme: español, portugués y francés tratan de usted, el italiano de tú. Se corrigieron tres mensajes en español y portugués que decían lo contrario.
- Mientras un diálogo muestra su vista previa, los espacios llegan a todos los campos de texto, también al cuestionario y al chat, y casillas y botones aceptan la barra espaciadora.
- Al «Escalar», un cuerpo sigue sobre la placa en vez de hundirse bajo ella, y la vista lo vuelve a encuadrar cuando crece.
- Algunos avisos que se refieren a un paso lo abren para cambiarlo, por ejemplo «Cambiar tamaño» tras «Llevar a la cota».
- Una línea de resumen del informe como «Reducir al volumen de impresión» es un solo paso de deshacer para todos los cuerpos.
- La ayuda de una operación salta en el manual directamente a su entrada, y la referencia nombra campos y opciones como aparecen en el diálogo.
- Si otros programas tienen el ordenador ocupado, «Cancelar» detiene un cálculo largo en menos de un segundo en lugar de pedir un reinicio tras varios segundos.
- Un modelo de lenguaje local puede dar doce pasos en lugar de ocho por encargo en el chat y resuelve así más encargos de varias partes.
- El panel de selección vuelve a caber en su columna, y la columna de medidas del árbol muestra la medida entera, como «Ø5,19 mm» en vez de «…».
- En un taladro, «Cambiar característica» abre directamente «Cambiar orificio» con vista previa, en vez de solo remitir a él.
- Al pulsar «Aplicar» durante una vista previa en curso, Solidon calcula el cambio una sola vez. Antes lo calculaba después una segunda vez.
- La vista de diferencias muestra lo añadido y lo eliminado con un rayado en dos direcciones, de modo que se distinguen también sin color.
- Cuando Solidon pregunta la unidad de un archivo al abrirlo, las medidas aparecen en su unidad de visualización y con el separador decimal de su idioma.
- Si arrastra un archivo que Solidon no abre, por ejemplo de Blender, le indica cómo traerlo como 3MF, STEP o STL. El G-Code va a «Contrastar con el G-Code».
- Puede abrir varios archivos en un solo paso. Conservan su posición relativa, un Ctrl+Z los deshace todos, y los avisos de importación iguales aparecen agrupados en el informe.
- Sobre el historial, «Antes/después» muestra con un deslizador cada estado anterior. «Continuar aquí» inserta allí pasos nuevos, y los nombres de sus pasos se mantienen.
- Con «a», «Trasladar» lleva el centro, el centro de la base, una esquina o una característica a una posición fija, y «Girar» lleva el cuerpo a ángulos fijos, también con varios cuerpos.
- Si copia el enlace de la página de un modelo, ya aparece en el campo de «Modelo desde internet», y Solidon muestra el camino a través del navegador.
- Si un diálogo no puede aplicar, el motivo aparece también bajo sus campos, no solo en la franja sobre la vista.
- Tras Ctrl+Y, la línea de estado nombra el paso que se ha rehecho, igual que tras Ctrl+Z.
- Las miniaturas de ejemplos y bloques muestran la altura hacia arriba. Hasta ahora las piezas altas apuntaban hacia abajo en ellas.
- Los ejemplos incluidos se abren con su impresora y su material. Hasta ahora se calculaban para la impresora genérica.
- Si Solidon no puede guardar la opción «Incluir valores», el aviso aparece junto al interruptor.
- Si otros programas ocupan todos los núcleos en Windows, un cálculo con un modelo grande ya no se queda parado durante minutos.
- Las longitudes en los avisos usan el separador decimal de su idioma.
- Tras cargar un modelo grande, el indicador de carga permanece hasta que la vista muestra el modelo.
- Un clic en una línea del informe de comprobación selecciona sus cuerpos aunque la lista se desplace al hacer clic.
- Los números fijos se vinculan con un clic a una medida del proyecto, y el selector de placas nombra los cuerpos de cada placa y muestra entera la elegida.

## 0.5.1

### Imprimir y entregar al slicer

- En PrusaSlicer, ElegooSlicer, Bambu Studio, Creality Print y OrcaSlicer rige el perfil del fabricante. Solidon solo escribe lo que usted cambia o acepta de las sugerencias.
- El nivel «Estándar» imprime con las velocidades y aceleraciones del perfil del fabricante en lugar de frenar a 40 mm/s. En una Centauri Carbon 2, las piezas grandes tardan un 40-50 % menos.
- Las sugerencias aplicadas valen solo para la pieza que las necesita: soportes, brim y los valores de un ajuste, en cada slicer compatible. Los ajustes de impresión nombran las piezas.
- Si una pieza se imprime de pie sin soportes, «Orientar para imprimir» la deja de pie en vez de tumbarla sobre soportes. Un juego de minigolf de 16 piezas cabe así en una placa en vez de cuatro.
- Si una pieza no cabe en la cama en ninguna posición, los ajustes de impresión dicen ya antes de laminar en cuánto es demasiado grande y ofrecen «Dividir el modelo» y «Reducir al volumen de impresión».
- También donde las piezas de un modelo solo se tocan funciona «Dividir el modelo», y los conectores quedan bien orientados en sus agujeros en cada costura. Antes el informe mostraba ahí colisiones.
- Solidon toma el ángulo de voladizo del perfil del fabricante de su impresora: 60 en lugar de 45 grados en Elegoo, Bambu y Creality. Chaflanes y pendientes suaves ya no reciben soportes innecesarios.
- En paredes exteriores redondas, Solidon propone una «Costura en bisel», en cada slicer compatible. La impresión tarda así entre un 2 y un 4 % más.
- Si su slicer calcula el brim por sí mismo, como ElegooSlicer, Bambu Studio, Creality Print y OrcaSlicer, Solidon no propone uno propio. El del slicer da más borde a las piezas altas.
- Los niveles «Fino», «Borrador» y «Resistente» eligen ahora el proceso correspondiente de su slicer, por ejemplo «0.12mm Fine» con «Fino».
- Los ajustes de impresión muestran lo que se imprime: la base es el perfil del fabricante, y sus propios valores están marcados y se pueden restablecer uno a uno.
- La placa de impresión se elige en los ajustes de impresión y la temperatura de la cama la sigue. Si el fabricante no autoriza la placa para su filamento, Solidon lo avisa antes.
- Sin «Aplicar las sugerencias», ninguna pieza recibe ya un brim sin preguntar, ni al exportar ni al entregarla al slicer.
- Nueva sugerencia «Mantener libres los canales»: aplicada, la entrega bloquea los soportes en los canales en cada slicer compatible. La ventana de Cura recibe el bloqueo y los valores por pieza.
- Un techo sobre un canal de agua o un túnel ya no atrae soportes sobre el modelo. Si nada más los necesita sobre el modelo, Solidon los propone solo desde la cama.
- Los ajustes de impresión muestran sus sugerencias más rápido: en el soporte de taladro, a los 4,3 segundos en vez de 7,6.
- Los proyectos de 0.5.0 imprimen con la velocidad de su impresora. Lo que usted había ajustado en ellos se conserva.
- La velocidad de la primera capa vale ahora también para su relleno. Antes el slicer hacía el fondo a la velocidad del fabricante, 105 mm/s en la Centauri Carbon 2.
- Con PrusaSlicer, la impresión empieza ahora como con la propia Prusa: con nivelación de la cama, línea de purga y comprobación de la impresora.
- El PETG llega ahora a PrusaSlicer como PETG, ya no como PLA.
- En OrcaSlicer cada impresora recibe preseleccionada su propia máquina y su proceso estándar: la Sovol SV06 ya no recibe la versión High-Speed ni la Ender-3 V3 «0.12mm Fine».
- Nuevas: las Creality Ender-3 V3 SE y V3 KE. Hasta ahora una SE recibía los valores de la mucho más rápida Ender-3 V3.
- Las copias iguales las calcula «Orientar para imprimir» una sola vez, y termina el mismo juego de minigolf en menos de un tercio del tiempo.
- Los niveles de calidad del diálogo de impresión aparecen ahora en el idioma de la interfaz.
- La velocidad de desplazamiento también viene de la impresora: la Centauri Carbon 2 se desplaza a 500 en lugar de 150 mm/s, como en el propio perfil de Elegoo.
- Si ha medido el voladizo de su impresora, también el slicer pone soportes solo a partir de ese ángulo, mientras rijan la altura de capa y el ancho de cordón de la medición.
- También el informe calcula ahora los voladizos con el ángulo a partir del cual su perfil del slicer pone soportes.
- Si un brim, skirt o raft sobresale de la cama, Solidon lo indica al entregar al slicer y ofrece «Organizar sobre la cama».
- Si el slicer rechaza una pieza demasiado alta, Solidon indica ambas alturas y ofrece «Dividir el modelo», «Reducir al volumen de impresión» u otra impresora.
- Si el slicer rechaza una pieza que no cabe en su placa, Solidon indica el motivo y ofrece «Dividir el modelo», «Reducir al volumen de impresión» y «Organizar sobre la cama».
- Si Bambu Studio se queda colgado tras laminar, Solidon toma el archivo de impresión terminado en lugar de dar un error a los cinco minutos.
- Con Cura también se pueden laminar modelos grandes. Antes el proceso terminaba sin archivo de impresión, por ejemplo con la torre Eiffel de 313 000 triángulos.
- Si Creality Print solo puede laminar un 3MF en su ventana, Solidon lo dice y lleva a «Abrir en el slicer …».
- Si la primera capa tiene tramos estrechos, aunque sean unos pocos largos en una pieza grande, Solidon propone hacerla a 50 mm/s. Así las líneas cortas se adhieren mejor.
- Solidon solo propone un «Tiempo mínimo por capa» más largo donde su perfil no tiene ninguno. Antes, la sugerencia aparecía en casi cualquier pieza con chaflán o punta.
- Donde su slicer ya limita la velocidad según el caudal volumétrico, Solidon ya no propone un límite de velocidad propio.
- Si adopta los valores de un perfil de filamento y después cambia de filamento, vuelven a regir los valores del nuevo.
- La primera capa imprime ahora líneas tan anchas como el perfil de su impresora, normalmente 0,5 mm con boquilla de 0,4. Con Cura, el cabezal ya no va a paso de tortuga entre ellas.
- Con Cura, la impresión empieza ahora con el código de inicio de su impresora, como en el fabricante. Si Cura no conoce la impresora o el archivo no lo lleva, Solidon se lo indica.
- Con Cura, la primera capa usa ahora la aceleración del perfil del fabricante en lugar de la aceleración de impresión completa.
- Los soportes de Cura siguen ahora el patrón de los perfiles de fábrica: unidos, con un techo ligero y velocidad moderada.
- Con Cura, las paredes en voladizo se imprimen ahora más despacio, como en el fabricante. Las impresiones con muchos voladizos tardan hasta un 20 % más.
- Con Cura, el relleno se imprime ahora después de las paredes, y los desplazamientos evitan los soportes y retraen el filamento en trayectos largos.
- El perfil para la ventana de Cura corresponde ahora a la impresora configurada en Cura. Antes Cura lo rechazaba con algunas impresoras o no lo mostraba.
- Los ajustes de impresión ya no ofrecen el caudal volumétrico para Cura, porque Cura no lo lee.
- Los soportes de rejilla llegan al slicer como rejilla de verdad, con la dirección cambiando en cada capa, en lugar de líneas sueltas que se desplazan al imprimir.
- Si una pieza se apoya en muchos pies pequeños, Solidon propone un brim donde su slicer no calcula uno propio, aunque los pies juntos tengan superficie suficiente.
- Una franja estrecha e inclinada junto a la pared exterior ya no cuenta en el informe como un puente largo.
- Un rótulo que es una pieza propia pegada a una pared ya no empieza en el aire según el informe, y Solidon ya no propone soportes para él.
- El informe solo muestra ya el aviso de calibrar las tolerancias de su material en modelos con ajustes. Solo ahí las usa Solidon.
- La entrega a Cura transmite las primeras capas sin ventilador como arranque progresivo. Solo avisa si el archivo de impresión final difiere de verdad.
- Tras «Reducir al volumen de impresión», la pieza sigue apoyada en la cama. Antes se levantaba, y el informe la daba por flotante.
- Si una pieza solo cabe en la cama con un margen más estrecho, «Organizar sobre la cama» la deja en el centro en vez de sobresalir del borde, y el informe indica ese margen.
- En modelos grandes, «Dividir el modelo» encuentra la costura hasta el doble de rápido, y en los de varios colores en una fracción del tiempo. La división funciona como antes.
- Si Solidon divide un modelo automáticamente en tres o más piezas, los nombres se numeran y nombran los conectores, por ejemplo «Listón de pared 2 de 3 · Pasadores y agujeros».
- Un tornillo, tuerca o junta impresos del catálogo de bloques ya no cuentan en el informe como un cuerpo fragmentado. Es una pieza propia, y así está previsto.
- Los tornillos y tuercas impresos tienen holgura también en la cabeza y en el apoyo, y siguen siendo desmontables aunque se impriman con la pieza. Los proyectos antiguos avisan del cambio al abrirlos.
- Con un tornillo avellanado del catálogo de bloques, un cuerpo de caras y aristas se mantiene estanco al exportar: la pieza y el tornillo entran en el archivo cada uno cerrado.

### Editar taladros

- Un taladro con avellanado en un lado y chaflán en el otro se puede inclinar, desplazar y duplicar. Antes, Solidon lo rechazaba.
- Un taladro o avellanado inclinado ya no corta lo que está delante de su boca, como una nervadura o el panal de al lado.
- Un taladro avellanado en una cara curva se puede desplazar, también con un clic en la vista. Tras desplazarlo, inclinarlo o quitarlo, el punto antiguo queda a ras con la cara.
- Un taladro avellanado con el borde de entrada redondeado en una cara plana se puede desplazar, duplicar y quitar junto con el redondeo. Antes quedaba un hueco.
- Taladros ciegos, ranuras y ensanches en una cara inclinada, y taladros ciegos inclinados como un bolsillo para imán sin labio, quedan abiertos del todo en la boca. Antes quedaba una fina piel.
- Desplazar y duplicar avisan cuando la pared hacia el taladro vecino se vuelve demasiado fina o se rompe.
- Si un taladro sale por el lateral de la pieza tras desplazarlo, duplicarlo o inclinarlo, Solidon lo indica también en zonas escalonadas. Una copia que no se creó se detecta.
- Un taladro desplazado o duplicado de un archivo STL ya no avisa por error en placas finas de que ha dejado de ser pasante.
- En nervaduras y panales, un taladro inclinado ya no indica por error que sobresale del borde.
- Tras desplazar, inclinar o duplicar, el panel de características muestra las cotas que el resultado tiene de verdad.
- Taladrar, desplazar, «Cambiar orificio» y estirar a ranura dejan el modelo fuera del taladro tal como estaba. El reconocimiento posterior termina mucho más rápido en modelos grandes.
- Si en un cuerpo de caras y aristas, por ejemplo de un archivo STEP, un corte de taladro falla sin que se note, Solidon lo detecta y vuelve a calcular. Antes podía quedar un cuerpo roto.
- En cuerpos de caras y aristas, los pasos de taladro están listos en segundos: en una placa perforada de un archivo STEP, «Cambiar orificio» tarda 2 en lugar de unos 120 segundos.
- En cuerpos de caras y aristas, «Cortar una cavidad» ya no devuelve un cuerpo defectuoso.
- Una ranura se puede acortar. Estirada hasta su propio ancho, vuelve a ser un taladro redondo.
- El tirador del extremo de una ranura se agarra en cualquier punto de la abertura, y ya no salta hacia el puntero en el primer arrastre.
- Las ranuras se llevan consigo sus chaflanes y su boca oblicua al desplazarlas o duplicarlas. Antes, los chaflanes se quedaban en el sitio antiguo.
- Un bolsillo para imán del catálogo de bloques se puede desplazar, duplicar, multiplicar y eliminar, junto con el labio que sujeta el imán.
- En un bolsillo para imán, «Cambiar orificio» con «Incluir avellanado, escalones y estrechamiento» cambia diámetro y labio. «Solo diámetro del orificio» mantiene la abertura y avisa si queda estrecha.
- Si se coloca en ángulo respecto a la cara, la abertura de un bolsillo para imán, un orificio para tornillo o un asiento de rodamiento queda libre. Antes había una cuña de material encima.
- Si un bolsillo para imán o un colgador de ojo de cerradura queda inclinado respecto a la cara, Solidon avisa de que su labio solo sujeta por un lado y ofrece «Corregir la entrada».
- Si un bloque como un bolsillo para imán no elimina nada en el punto elegido, Solidon lo indica y aconseja hacer clic en la cara.
- En un bolsillo para imán con labio, «Estirar a ranura» también rechaza actuar en cuerpos de caras y aristas, en lugar de cortar el labio.
- Si coloca una rosca, un inserto termofijado o un alojamiento de tuerca en un taladro, el diálogo indica arriba el tamaño que encaja y preselecciona justo ese.
- En un avellanado, «Cambiar elemento» corta la nueva medida como si se hubiera avellanado así desde el principio. Antes, Solidon se negaba o dejaba una fina piel atravesando el taladro.
- Si piezas de un modelo están metidas unas en otras, Solidon las une antes de calcular, tal como se imprimirán. Volumen y taladros cuadran entonces, y el informe lo dice.
- Si agranda un taladro, la vista previa precisa muestra todo el material retirado, también en modelos grandes, con la vista en sección y en cuerpos con canales cerrados.
- Al escribir una cota en una figura grande, la vista previa aproximada aparece en menos de un segundo en lugar de hasta diecinueve, y la de un taladro en ella funciona.
- Si un paso en un modelo abierto solo calcula de forma aproximada y el volumen crece, el informe indica la desviación y ofrece «Reparar primero y volver a calcular».

### Redondear y achaflanar

- La elección de aristas «Horizontal», «Superior» o «Abajo» ya no incluye el borde de un taladro lateral. Si lo quiere, elíjalo aparte; los proyectos antiguos calculan como se guardaron.
- En un modelo importado, el borde de un taladro se redondea o achaflana tan hondo como en una pieza construida. Antes, con radios grandes, el redondeo salía hasta un quinto más plano.
- Si la cota no cabe en todas las aristas de una elección como «Todos» o «Vertical», Solidon trabaja las que sí caben y muestra las demás con «Mostrar el punto», en vez de negarse.

### Cotas en la vista

- De taladro en taladro, las cotas en la vista aparecen en un tercio del tiempo. El primer clic en una característica ya no congela la ventana, ni siquiera en modelos grandes.
- Un clic en un taladro ya no muestra imágenes intermedias: el panel de selección y la tarjeta de cotas aparecen directamente en su sitio, sin saltar.
- Un clic en las flechas de un taladro seleccionado ya no retiene la selección: el siguiente taladro se puede seleccionar como siempre.
- Escape en las cotas de la vista descarta el borrador y quita la selección, como «Cancelar».
- Un clic en «Aplicar» ya no se pierde en silencio, y las cotas que no ha escrito se quedan exactamente como se midieron.
- Un taladro empezado ya no se pierde por el camino: un clic en el informe, un cambio de herramienta o Ctrl+Z piden primero aplicarlo o cancelarlo.
- Al escribir una coordenada, los campos de cota ya no desaparecen tras la segunda cifra.
- En modelos grandes, «Medir el espesor de pared» responde unas cuatro veces más rápido.
- Un clic en el centro de un taladro avellanado selecciona el taladro y no su avellanado, y las cotas nombran su arista por el lado, como «Arista exterior izquierda» en vez de «Arista exterior 4».
- Con una arista o una distancia seleccionada, el panel de selección ya no dice «Ningún elemento seleccionado …».

### Reconocimiento

- Las características se reconocen solas hasta 1,5 millones de triángulos. Hasta cinco millones, Solidon pregunta antes e indica la memoria necesaria y la duración en su ordenador.
- Rechazado el reconocimiento completo, se recupera con «Reconocer todas las características» en el informe o en la línea de comandos. Si tarda, «Cargar sin reconocimiento de características» lo omite.
- En modelos grandes, «Detectar detalles en un punto» encuentra caras donde antes indicaba demasiados triángulos. El punto también se elige con el teclado.
- En modelos grandes, «Detectar detalles en un punto» empieza a buscar enseguida. Antes recalculaba primero todo el modelo, 40 segundos por intento en el dragón del mausoleo.
- Los modelos grandes y las retículas se reconocen mucho más rápido: una cama de casa de muñecas generada, de 1,2 millones de triángulos, en 27 s en vez de 174. Cancelar actúa en pocos segundos.
- Las copias y las piezas giradas o desplazadas heredan las características de su original sin buscarlas de nuevo. Un proyecto con muchas piezas iguales se calcula así en menos de la mitad del tiempo.
- Tras un taladro, la cara de un cuerpo construido indica su tamaño actual, y un taladro nuevo ya no falta en el árbol cuando antes se cambió otro.
- Rótulos y tirantes aparecen en el árbol como lados redondeados en lugar de decenas de redondeos con radios cambiantes.
- Los contornos de arcos y rectas se reconocen arco a arco con su radio. «Convertir en caras y aristas» es así mucho más rápido.
- Un tetón escalonado ya no cuenta como rosca. Vuelven los cilindros y taladros que esa confusión se había tragado.
- El labio de un bolsillo para imán se llama estrechamiento en el árbol y nombra su abertura. Ninguna acción lo convierte ya en avellanado.
- Tras «Refinar las aristas», Solidon reconoce redondeos, taladros y rótulos igual que en el original, incluso tras otro taladro. Los redondeos iguales conservan su nombre, también tras «Trasladar».
- Un patrón alrededor de un mango redondo, como un moleteado en una tapa, conserva su centro y su dirección al seguir editando.
- Tras «Dividir» y «Recortar», una cara dividida conserva su nombre en la parte más grande, y los ajustes en ella siguen siendo válidos.
- Si hace clic en el borde de un taladro tumbado, se llama «Vertical», tal como está en realidad.
- Si un modelo tiene más de 5 000 características, Solidon conserva las más grandes en lugar de quedarse sin ninguna. Escalar no revuelve sus nombres.
- Un bloque con una sola característica se llama en el árbol igual que en el historial, como «Bolsillo para imán» en vez de «Orificio ciego 1».

### Importar y reparar

- Un modelo grande aparece en la vista nada más importarlo, y sus características llegan después. Antes solo aparecía al terminar el reconocimiento.
- Un 3MF con varias placas de Bambu Studio, OrcaSlicer o ElegooSlicer pone cada pieza en su placa, en su sitio. Antes iban todas a una, muchas fuera de la cama.
- Un 3MF con varias placas que se añade a un proyecto conserva sus placas y las coloca detrás de las existentes.
- Un modelo más va al primer sitio libre de las placas, o a una placa nueva, y se queda allí. Antes conservaba las coordenadas de su archivo, casi siempre fuera de la cama.
- También un modelo de «Generar modelo» queda apoyado en la cama, en el primer sitio libre de las placas.
- Un modelo sin colores propios conserva el color del cuerpo tras cerrar sus agujeros. Antes se volvía gris, y «Convertir la textura en filamentos» hacía con él un filamento gris.
- Si a un modelo le falta un trozo de pared de taladro o parte de un cono de avellanado, Solidon cierra el hueco como pared, no como tapa a través del taladro.
- Las costuras abiertas se cierran al importar y reparar sin unir piezas que solo se tocan. Un modelo intacto queda sin cambios.
- Los solapamientos los resuelve ahora «Reparar» por sí solo. Si las piezas de un modelo importado están metidas unas en otras, el informe ofrece «Resolver solapamientos».
- Una superficie sin grosor queda abierta y ofrece «Dar grosor». Una abertura grande indica su sitio con «Mostrar el punto», y «Dejar abierto» deja abierta solo esa.
- Tras cerrar una abertura al importar, «Mostrar el punto» rodea toda la cara nueva con un color propio.
- Una pieza vuelta del revés junto a un cuerpo hueco se endereza sin perder la cavidad. Una pieza dentro del material de otra se indica en lugar de adivinarse.
- El informe tras importar es más corto: los hallazgos que el resultado desmiente desaparecen, y donde se puede hacer algo hay un botón en lugar de un consejo.
- El mapa de defectos de malla muestra las zonas sanas en el color del cuerpo, para que cada defecto destaque, y lleva «Reparar» en la leyenda. Si hay un solo cuerpo, lo selecciona solo.
- La búsqueda de solapamientos llega ahora al final también en modelos con abanicos de triángulos estrechos. Mapa de defectos y reparación ven entonces todo el modelo.
- Un 3MF de PrusaSlicer ya no carga modificadores, bloqueadores ni reforzadores de soportes como material macizo. Un volumen negativo se resta de la pieza.
- Con «Refinar las aristas» se conservan todas las características y salen hasta cuatro veces menos triángulos: un soporte de taladradora con aristas de 1 mm en cinco segundos en vez de catorce minutos.
- Un modelo cerrado sigue estanco y conserva sus colores de filamento. Con demasiados triángulos, Solidon indica una longitud de arista que funciona de verdad.
- La vista previa de «Refinar las aristas» y «Reducir triángulos» está lista en segundos en lugar de congelar la ventana, y una longitud demasiado fina se rechaza de inmediato.
- Si un modelo es demasiado fino para «Refinar las aristas», el informe ofrece «Reducir triángulos y volver a intentarlo» con una cifra que realmente funciona.
- Si «Suavizar» fuera a volver del revés un cuerpo, Solidon lo indica y ofrece «Refinar las aristas y volver a intentarlo» con una longitud de arista que funciona.
- Los conjuntos grandes se importan más rápido: la reparación al importar un barco pirata de 1,2 millones de triángulos tarda alrededor de un 30 % menos.
- Al abrir archivos 3MF grandes, la ventana sigue respondiendo, también mientras se lee el modelo.
- Si importa una copia renombrada de un archivo ya abierto, el cuerpo lleva el nombre nuevo. Antes se llamaba como el primer archivo.
- En mallas grandes, «Cerrar superficie abierta» calcula en segundos: 1,8 en vez de 24 segundos con 122 752 triángulos.

### Manual y sitio web

- Quince guías muestran paso a paso, con imágenes de la aplicación, cómo comprobar, imprimir y reparar un modelo, construir, dividir y rotular una pieza o imprimir a dos colores.
- El manual empieza en «¿Por dónde empiezo?» y lleva desde ahí a cada guía. F1 en el diálogo de una operación abre su guía o su entrada.
- Una imagen de conjunto explica la ventana: cada número de la imagen señala una zona.
- La búsqueda del manual encuentra la página adecuada también con palabras cotidianas, la muestra primero y la abre donde aparece la palabra.
- La referencia indica en cada operación dónde se encuentra en el menú o en el panel de selección.
- Las páginas explicativas son un tercio más cortas. Si hay una guía con imágenes sobre su tema, el enlace aparece al final de la página.
- En el sitio web y en el PDF, el manual está organizado como en la aplicación, de los primeros pasos a la consulta. En el PDF, los marcadores llevan a cada capítulo.

### Manejo y sistema

- Los cálculos grandes, como la vista previa o «Refinar las aristas», van en un proceso aparte: la ventana responde y «Cancelar» actúa al instante. Para ello corre un segundo proceso de Solidon.
- Al cargar y en cálculos largos, un reloj cuenta el tiempo transcurrido aunque el progreso se detenga, y el tiempo restante ya no salta cuando empieza una nueva parte del cálculo.
- La copia de seguridad automática funciona en segundo plano y ya no detiene la ventana, ni con modelos grandes. Si no se puede escribir, Solidon lo dice.
- Un modelo en una unidad lenta o que no responde ya no congela la ventana al abrirlo.
- Si un archivo de «Abiertos recientemente» se ha movido, Solidon lo dice y ofrece «Elegir otro archivo».
- Un archivo que no se pudo leer ya no acaba en «Abiertos recientemente», y el siguiente archivo ya no anuncia su nombre al cargar.
- Un archivo sin modelo legible ya no se queda como primer paso, en el que cada archivo siguiente fallaba con «La cadena se detiene».
- Los proyectos abiertos recientemente en la página de inicio se abren con un clic.
- Sin nada seleccionado, el panel de selección ofrece lo que se aplica a todos los cuerpos: «Orientar para imprimir», «Organizar sobre la cama» y «Comprobar solapamientos».
- Tras «Dividir el modelo», todas las piezas quedan completamente a la vista.
- Cada paso detenido en el informe tiene un botón: «Corregir la entrada» lo abre con el cursor en el campo afectado.
- Tras «Dividir el modelo», el informe dice en una frase que los trozos siguen juntos, en vez de en más de veinte líneas, y las líneas del cuerpo antiguo ya no llevan botones vacíos.
- Un dibujo trazado libremente sin cota ya no genera un aviso en el informe.
- Si el informe solo tiene avisos informativos, arriba dice «Lista para imprimir», y un aviso de configuración ya no aparece preseleccionado como una advertencia.
- Las advertencias del informe llevan un botón: «Mostrar el detalle» en un ajuste que no encaja, «Abrir los ajustes de impresión» en avisos de cama, soportes, boquilla y brim.
- Un informe de error nombra las carpetas de su directorio de usuario sin su nombre de usuario, incluso si Solidon está instalado allí.
- En «Primeros pasos», la impresora de su slicer aparece nada más abrir. Antes la sugerencia llegaba al cabo de unos segundos, y «Terminado» tomaba hasta entonces la impresora genérica.
- Tras importar, la barra de título lleva el nombre del modelo en vez de «Sin título», y «Primeros pasos» nombra los slicers por su nombre y no por el del archivo.
- El slicer se elige en los ajustes de impresión encima de los perfiles, aunque esa sección esté plegada.
- La impresora que elija en los ajustes de impresión pasa también al siguiente proyecto nuevo. Si su slicer está en otra impresora, el diálogo la ofrece con un clic.
- Si elige otra impresora u otro slicer, el perfil de máquina recordado del anterior deja de valer.
- En la barra de parámetros y en el diálogo de una operación, un número tecleado fuera de los límites se rechaza en vez de recortarse en silencio, y Solidon indica el límite.
- La pregunta antes de borrar un paso nombra los pasos dependientes que se van con él.
- El historial nombra un parámetro cambiado con su etiqueta y muestra el valor antes y después.
- El tirador de una cara seleccionada muestra solo la flecha con la que se desplaza.
- Sin texto, «Aplicar texto» dice que falta el texto en vez de dar la vista previa por no disponible.
- Tras dibujar, a la derecha vuelve la pestaña de antes, por ejemplo el informe. Hasta ahora aparecía el chat, y «Entregar al slicer …» quedaba oculto.
- La «Paleta de comandos …» encuentra operaciones en cada idioma también con palabras cotidianas, como «copy» o «calamita». Hasta ahora solo conocía esas palabras en alemán.
- Al guardar con «Guardar la selección como bloque …», Solidon comprueba el grosor de pared del bloque muchas veces más rápido.
- En todas las traducciones, «Separar» y «Dividir» se llaman ahora de forma distinta, las teclas como en el teclado, y la interfaz italiana tutea en todas partes.

### Asistente con modelo local

- La elección de modelo recomienda también un modelo más pequeño para tarjetas desde 10 GB de memoria gráfica e indica para cada uno la memoria que ocupa y cómo resuelve encargos de varias partes.
- El asistente recibe en detalle solo las acciones que encajan con la petición. Así queda sitio para el historial y la respuesta, y los encargos salen bien mucho más a menudo.
- El modelo local se queda cargado tres minutos tras una respuesta, y la siguiente pregunta ya no espera a que arranque.
- Una respuesta que no encuentra fin se corta tras una longitud fija y se indica como cortada, en lugar de ocupar la tarjeta gráfica hasta el límite de diez minutos.

## 0.5.0

### Reconocimiento

- El reconocimiento en modelos importados es muchas veces más rápido: una placa con 200 000 triángulos y sus agujeros está lista en un segundo, donde una forma libre lisa tardaba minutos.
- Las caras pequeñas como la punta de una leva, los agujeros cortados y los chaflanes de boca se reconocen igual en una malla y en un cuerpo exacto.
- Las cavidades cerradas y las cámaras de aire anidadas se reconocen como un todo. Un agujero que lleva a una cavidad ya no aparece como fantasma.
- Las roscas importadas se miden: paso, número de entradas, sentido derecho o izquierdo y diámetro nominal. Las piezas reflejadas conservan el sentido correcto.
- Conos, esferas y anillos conservan sus medidas reales, y el panel de características dice de dónde viene un valor: medido, ajustado o del paso.
- Una pieza reflejada, escalada o repetida en patrón lleva consigo sus características. Las características caducadas ya no quedan junto a las nuevas.
- Los archivos STEP con superficies de forma libre mantienen sus agujeros editables, también tras guardar, reabrir y deshacer.
- Tras un cambio, cada característica que sigue existiendo conserva su nombre. Si dos candidatas entran en cuestión, Solidon pregunta en vez de adivinar.
- Un clic en un taladro de un modelo con 360 000 triángulos responde en la cuarta parte del tiempo.
- Un avellanado que toca dos ranuras por igual sigue siendo una cara cónica en lugar de desaparecer en una de ellas.
- Si un modelo consta de varias cáscaras y no se puede leer con seguridad si alguna encierra aire, el informe lo indica como advertencia.
- Un modelo cerrado libera su memoria; antes quedaban unos cientos de megabytes por modelo.
- Un modelo con muchas caras pequeñas, como un patrón de panal, conserva sus taladros y redondeos. Antes no mostraba ni una sola característica.
- Un campo de 1400 tetones se reconoce en cuatro segundos en lugar de doce.

### Patrones

- Un panal, un moleteado, nervios, ondas u hoyuelos aparecen en el árbol como un patrón con paso, ancho de celda y profundidad, también alrededor de un mango. Antes eran cientos de caras.
- Un patrón se elimina con un clic o se vuelve a poner con nuevo paso, ancho de celda y profundidad. Las celdas se quedan donde estaban.
- Una textura alrededor de un cilindro sigue la curvatura: las ranuras tienen la misma profundidad y un patrón en toda la circunferencia cierra sin costura. El paso se ajusta al valor que encaja.

### Dibujo

- Dibujar sobre una pieza elegida muestra solo esa pieza en la vista; las demás quedan ocultas hasta que «Mostrar vecinas» las devuelve.
- Extruir sobre una cara elegida ahora une el nuevo cuerpo en vez de detenerse; antes nunca pasaba del boceto.
- Una cavidad corta donde usted la ha dibujado, aunque la cara no esté centrada en la pieza.
- Redondear y biselar un rectángulo acotado deja sus medidas sin cambios.
- Si dibuja con varias piezas elegidas, Solidon pregunta en cuál; el destino se puede cambiar en cualquier momento en la barra.
- Escape ya no descarta un boceto que ha empezado.
- Un boceto ya extruido se puede reutilizar para la siguiente cavidad, sin volver a dibujarlo.
- Un clic en una cara ofrece directamente «Dibujar aquí» y «Dibujar agujero o hueco».

### Editar sobre el modelo exacto

- Los cuerpos básicos se crean siempre con caras y aristas reales. La casilla «Editar caras y aristas más tarde» ha desaparecido; los proyectos antiguos se calculan sin cambios.
- Agujero, ranura, avellanado, tetón, cúpula y tronco de cono se mantienen exactos en un cuerpo exacto al desplazarlos, duplicarlos, girarlos o eliminarlos.
- Los cordones y las gargantas se pueden desplazar, duplicar, girar, cambiar y eliminar. Una rosca se puede cambiar y cerrar.
- Una rosca obtiene su contraparte en la otra pieza con solo pulsar un botón, en la medida de tabla y como un único ajuste.
- Todos los bloques de la biblioteca se construyen exactamente sobre un cuerpo exacto, desde el atornillado hasta la ranura de junta.
- Tras cambiar un radio, Solidon redondea la arista correcta, incluso cuando dos redondeos están muy cerca.
- Si dos aristas están en el mismo lugar, Solidon pregunta cuál quiere decir en vez de tomar una.
- Aplicar espera hasta que la vista previa muestra el resultado actual. Un clic sobre una imagen caducada no escribe nada erróneo.
- Los colores de filamento se conservan en los cuerpos exactos y siguen cada nuevo mallado.
- El volumen y el área de un cuerpo exacto llegan en milisegundos en lugar de segundos.
- Insertar una rosca tardó entre 0,38 y 0,41 segundos durante la medición, frente a entre 8 y 13 segundos. La operación completa creó un perno roscado M6 × 1 de 12 mm de longitud en 0,55 segundos.
- Unir, Restar y Colocar sobre la cama ya no preguntan si convertir los cuerpos exactos. Siguen siendo exactos.
- Al desplazar un taladro no quedan triángulos sobrantes en el sitio antiguo, y un avellanado oculto no pierde nada de su volumen.
- Reparar deja intacto un modelo limpio, también en el cuerpo exacto.
- La contraparte de una rosca se construye en segundo plano. Mientras tanto la ventana sigue utilizable.

### Taladrar y medidas en la vista

- Un agujero al que se hace clic muestra sus medidas de inmediato en la vista: distancias a las aristas, centro y diámetro, con campos numéricos para escribir.
- Los campos de medida están junto a la pieza en lugar de sobre ella, y sus líneas no se cruzan.
- La referencia de una medida, arista, centro o eje, se puede cambiar con clic derecho sobre la medida o haciendo clic en el modelo.
- Lo que está en la vista no se repite a la derecha en el panel de selección.
- Tras estirar un agujero hasta convertirlo en ranura, las medidas se mantienen, aunque gire la vista. Los botones para estirar están siempre en el agujero elegido.
- Al elegir un agujero, la vista 3D podía fallar en algunas tarjetas gráficas. Está corregido.
- Un arrastre en el asa sobrevive a un redibujado en mitad del arrastre, y un paso de rueda sobre un campo de cota amplía la vista en lugar de cambiar la cota.
- El primer Escape al elegir una referencia solo retira la elección; los valores tecleados se conservan.
- Con «Llevar avellanado y escalones», el taladro también se puede desplazar mediante las cotas. Vástago y avellanado se mueven juntos, en un solo paso.
- Si Solidon rechaza una cota, el motivo aparece sobre la vista previa en lugar de solo «no se pudo calcular».
- Los campos de cota se quedan donde estaban cuando cambia un valor. La cota en cuyo campo escribe se ilumina en la vista.
- Los tiradores para la ranura también funcionan mientras las cotas del taladro están en la vista: Aplicar estira entonces la ranura — con un diámetro nuevo al lado en un solo paso, con el nuevo ancho.

### Historial

- En el historial ahora se puede insertar un paso nuevo antes de uno existente, no solo añadirlo al final.
- Un paso del historial se puede arrastrar con el ratón a otro lugar, o moverlo línea a línea.
- Un paso se puede desactivar y volver a activar más tarde sin borrarlo; los pasos dependientes quedan en reposo con él.
- Si un paso posterior hace referencia a una característica que el reordenamiento ha renombrado, Solidon la sigue y lo indica.
- Si reordenar el historial detendría un paso posterior, Solidon lo rechaza y no cambia nada.

### Comprobar e imprimir

- Han llegado las impresoras de resina: dos equipos genéricos por volumen de impresión están en la lista, y una propia se puede crear con tamaño de píxel y pared mínima.
- Un proyecto de resina ya no recibe consejos sobre boquilla, brim o puentes, y la pared mínima viene del perfil de la impresora.
- El archivo se puede abrir en cualquier programa, también en el slicer de un fabricante de resina cuyos ajustes Solidon no conoce.
- Los cuerpos exactos se mallan tan finos como lo exigen los píxeles de una impresora de resina; el informe nombra la medida.
- Los ajustes comprueban los cuerpos reales en su posición de montaje. La exportación se puede cancelar antes.
- La desviación de forma muestra qué caras de un mallado están a qué distancia del original.
- Si un grosor de pared se estrecha en cuña, Solidon lo dice y aconseja imprimir primero la pared exterior.
- La búsqueda de orientación pone una rejilla de borde estrecho sobre su borde, y una rejilla de travesaños cortos no necesita soportes.
- La ficha para el asistente dice sobre el punto elegido lo mismo que el panel de características.
- La desviación de forma de una caja con tapa se calcula en una décima de segundo en lugar de doce.
- Las piezas separadas para imprimir ya no reciben una advertencia sobre su posición de montaje. El ajuste informa solo de lo que ha medido.
- La búsqueda de orientación en un modelo con más de un millón de triángulos tarda cinco segundos en lugar de medio minuto.
- Las distancias muy pequeñas aparecen en el mapa de análisis como decimales, no como potencias de diez.
- La desviación de forma en redondeos y anillos es tan precisa como en planos y cilindros, y el mapa se calcula más rápido que antes.
- El ventilador de pieza vuelve a seguir la curva del perfil de la impresora, en vez de ir a máxima velocidad en cada capa.

### Importar

- Un conjunto importado se puede colocar sobre la cama como un todo con un clic. Las piezas conservan su posición relativa.
- Un glTF sin un tamaño plausible ya no se toma por metros. Solidon pregunta la unidad y muestra las medidas de cada lectura.
- Un modelo con zonas abiertas se cierra al leerlo en vez de solo avisarlo: agujeros en la malla, caras invertidas, aristas con tres caras. Las aberturas grandes se nombran aparte en el informe.
- Una pieza hueca importada se puede rellenar con una celosía: Solidon determina el hueco interior a través del respiradero y dice que lo ha determinado así.
- Reducir triángulos ya no rompe los modelos cerrados. Donde la forma no permite otra cosa, el informe indica en cuántas piezas se ha dividido el modelo.
- Reducir triángulos alcanza ahora su objetivo también en casquillos, anillos y carcasas con aberturas.
- Un ensamblaje STEP importado llega como cuerpos independientes con su propio nombre y colores de cara, en lugar de un conjunto fundido en uno solo.
- Antes de incorporar un ensamblaje STEP, usted elige qué cuerpos necesita; una pieza reflejada sigue siendo un reflejo.
- La exportación STEP escribe nombres y colores de cara en el archivo; una pieza vuelta a leer conserva su nombre sin cambios.

### Manejo y sistema

- Cada acción confirma brevemente su resultado donde ha hecho clic, además de en la línea de estado.
- Un error del programa deja un registro local que se adjunta al informe de soporte. Nada se envía por sí solo.
- La configuración de «Modelo a partir de texto» descarga por sí misma el modelo de imagen que falta en vez de remitirle a una carpeta.
- Solidon arranca en la mitad de tiempo.
- Con una característica seleccionada se mantiene la descripción emergente, y una indicación sobre el asa ya no borra el último acuse.
- Si un paso del asistente detiene la evaluación, la propuesta lo retira por completo y muestra el estado anterior.
- Mover o girar un modelo de 200 000 triángulos responde en medio segundo en lugar de ocho.
- Deshacer responde al instante en lugar de tras dos segundos y medio.
- Al cambiar el diámetro del taladro en la placa perforada, la primera vista previa apareció en 0,57 segundos durante la medición, y cada siguiente en 0,13 segundos.
- El vaciado fue entre un 7 y un 25 por ciento más rápido en los tres modelos medidos.
- Una entrada del menú y un aviso discreto en la vista llevan a apoyar Solidon voluntariamente por PayPal o GoFundMe.
- La tarjeta de la encuesta muestra ahora los colores correctos también en el tema claro.

- La aplicación y el instalador de Windows están firmados digitalmente. La firma confirma quién los publica y permite detectar cambios posteriores.

## 0.4.4

### Editar

- El ángulo de desmoldeo alcanza ahora todas las caras verticales, también las estrechas, y funciona en modelos importados.
- La fusión suave deja caras laterales lisas en lugar de bordes deshilachados.

### Seleccionar y manejar

- Una bobina del inventario de filamentos puede tener hasta cuatro colores. Bambu Studio, OrcaSlicer y ElegooSlicer reciben todos los colores; los demás slicers, el primero.
- Una arista seleccionada muestra solo las acciones que hacen algo en una arista.
- Sin selección, el camino a los bloques sigue visible.
- El campo de búsqueda solo aparece donde hay algo que encontrar.
- Un tabique del organizador lleva a su editor de compartimentos en lugar de a las acciones de su cara.
- El diálogo para colocar un taladro indica que el punto se elige en la vista.
- En el diálogo «Generar modelo», el campo de descripción conserva su altura aunque aparezca el aviso sobre el programa adicional que falta.

### Mover y comprobar

- Las sugerencias de impresión llegan mucho más rápido: una figura de 2,3 millones de triángulos en segundos en lugar de minutos, y abrir el diálogo de impresión por segunda vez no vuelve a medir.
- Una bobina importada de otro tipo de material que ninguna pieza usaba cerraba el slicer sin decir nada. Ahora cada bobina de una placa recibe un perfil completo.
- Si el slicer no tiene un perfil del fabricante para su tipo de material, el diálogo de impresión lo dice y usa los valores de Solidon, no un perfil de otro material.
- Dos cuerpos pueden empujarse uno dentro de otro para unirlos o fusionarlos suavemente. Solo se devuelve lo que queda fuera del área de impresión.
- Si un ajuste apunta a una característica que ya no existe, un botón lleva al historial.
- Orientar para imprimir y Organizar sobre la cama ponen piezas de distintos filamentos en placas propias, para que una boquilla no purgue sin parar. Varias boquillas se indican al imprimir.

### Inventario de filamentos

- Una anulación en el historial de movimientos se puede revertir de nuevo, con el mismo botón.
- Cambiar solo el nombre o la ubicación de una bobina ya no cuenta como nuevo recuento; sus registros siguen siendo anulables.
- Tras una anulación, «Registrar sin preguntar» registra de verdad una nueva impresión en vez de decir solo «registrado».
- Las fechas de compra y apertura tienen un calendario en su idioma. Una bobina rechazada vuelve al diálogo en vez de desaparecer.
- La importación desde el slicer crea una bobina nueva si tiene el mismo nombre y otro color, en vez de recolorear la suya.
- Si el archivo del inventario no se puede leer, un botón recupera el último estado: Solidon lo guarda solo en cada escritura.
- La página de detalle muestra cantidad restante, fecha de compra y precio; el código de ocho caracteres solo aparece si dos bobinas se llaman igual.

## 0.4.3

### Reconocimiento y edición

- Se reconocen mejor los taladros ciegos poco profundos, las caras pequeñas y las roscas cortas. Los fondos de los alojamientos para imanes pertenecen a sus taladros.
- Cambie el diámetro junto con el avellanado y la entrada conservando las medidas previstas. El fondo sigue asociado incluso tras cambios grandes de diámetro.
- Reconozca elementos en un punto elegido de una malla grande y edítelos al instante. El reconocimiento y el cambio se deshacen juntos.
- La selección y la vista previa muestran el cuerpo completo. Contornos y etiquetas identifican la zona elegida; las letras sin cambios no muestran manchas naranjas.
- Las aristas se pueden seleccionar en cualquier cuerpo y redondear o achaflanar, también en modelos importados.
- Los taladros, cilindros y redondeos se construyen con los mismos puntos en Windows, macOS y Linux. Un proyecto se reconoce y se edita igual en cualquier equipo.

### Construcción

- Los organizadores admiten medidas vinculadas, divisores editables por separado y celdas repetidas. Bandeja, borde, fondo y pie amplían la biblioteca.
- Los campos de agujeros, ranuras y hexágonos siguen una región dibujada. Se respetan las zonas reservadas, los márgenes y los puentes mínimos.
- Las abrazaderas de perfil constan de dos carcasas y dos insertos ajustados. Admiten perfiles redondos, ovalados o dibujados; los insertos pueden sustituirse después.
- Un dibujo cerrado o una abertura elegida crea una ranura de sellado y una junta separada. Puede elegir materiales, sección y saliente; se comprueban las paredes restantes.
- Los patrones superficiales llegan al borde de la cara y dejan libres los taladros. Puede editar los patrones existentes desde el panel de selección.
- Recortar conserva un lado de un plano y cierra la cara de corte: para paredes traseras lisas y paredes a una misma altura. Los redondeos junto a paredes algo inclinadas vuelven a poder editarse.

### Importación y manejo

- Seleccione visualmente los contornos SVG y DXF antes de crear el cuerpo. Los archivos GLB y GLTF conservan sus medidas y orientación correctas.
- Las medidas del proyecto siguen actuando en los bocetos de piezas y sus vistas previas de colocación. El encuadre incluye todas las placas de impresión visibles.
- Puede quitar filamentos de la estantería. Los primeros pasos empiezan por el slicer; los comentarios se abren rápido y preparan sus adjuntos en segundo plano.
- Supr sobre una cara elimina el cuerpo y lo indica; Ctrl+Z lo recupera. Con una vista rasante, un cuerpo arrastrado sigue al puntero, y la cara elegida se mantiene en el primer clic del boceto.
- El chat local recibe una ventana mayor y ya no recorta su solicitud.
- El diámetro de la boquilla se ajusta en la impresora. La entrega elige entonces la máquina adecuada en el slicer, aunque allí esté seleccionada otra boquilla.
- Reparar cierra los modelos que se tocan a sí mismos en una arista, en lugar de abrirlos más.

## 0.4.2

### Dibujo

- Dos clics crean un polígono regular: primero el centro, luego una esquina. El número de esquinas se elige antes: de tres a doce. Un diámetro escrito queda como cota.
- Una ranura surge de dos clics en los centros de sus extremos redondeados; el ancho está al lado en la barra. Ambos extremos mantienen el tamaño y los flancos, rectos.
- Cuatro condiciones nuevas: ángulo en grados entre dos líneas, igual longitud o tamaño, punto en el centro de una línea, y concéntrico para dos círculos o arcos.
- Un punto arrastrado se queda en el puntero y sus vecinos lo siguen: una esquina del rectángulo arrastra ambos lados, una línea estira la forma. Antes la esquina solo llegaba a mitad de camino.
- Un rectángulo hecho con clics es libre: sin punto fijo ni cotas mientras no las escriba. Una anchura o altura escrita se queda como cota, como en Fusion.
- Las formas del menú se pueden desplazar; las cotas de la entrada del menú se mantienen. Para cambiar una cota en la vista, haga doble clic en su tarjeta.
- Redondear y chaflán en el editor de bocetos: señalar una esquina, escribir el radio o la medida, hacer clic. El redondeo sigue en su esquina al arrastrar; el chaflán crea un borde inclinado.
- Si una restricción sujeta un punto, la línea dice cuál — y que un clic derecho en el punto la suelta. Antes el punto se quedaba quieto sin más.
- Fijo significa fijo: un punto fijado ya no sigue el arrastre. Las líneas exactamente horizontales o verticales se mantienen así, aunque después arrastre una esquina.

### Construir y modificar

- Girar un agujero rasgado lo gira, en lugar de cortar un segundo cruzado encima. Y al editar uno que usted mismo estiró se cambia ese paso; el historial no recibe un segundo.
- Un STL que exporte tras «Cambiar orificio», «Mover elemento» o «Aplicar un chaflán» en un modelo importado llega cerrado al slicer. Antes, la costura se abría al soldarla el slicer.
- Si en el chat nombra solo un eje — «taladro a x = 20» —, el agujero se mueve solo ahí. Antes saltaba a cero en los otros dos ejes.
- Redondear avisa de antemano que un cuerpo exacto admite un radio menor que una malla, y qué ayuda entonces: un radio menor o seguir trabajando sobre la malla.
- Abrir el mismo archivo dos veces da dos nombres distinguibles: «soporte» y «soporte 2». Antes ambos cuerpos se llamaban igual, en el árbol y en el informe.
- Los mensajes que remiten a los valores de la derecha nombran la ventana como se llama: Selección. Antes decían «panel de características», y así no se llama ninguna ventana.
- El paso «Reducir triángulos» avisa cuando una pieza ya tiene menos triángulos que la cantidad indicada: entonces no hay nada que reducir. Antes se quedaba igual, sin una palabra.
- El paso «Dar una postura» sin esqueleto avisa de que los huesos se crean en el editor de esqueleto: dos clics por hueso. Antes el paso no movía nada, en silencio.
- Un taladro que desplace, gire, duplique o modifique lo indica cuando con ello sobrepasa el borde de la pieza — como al taladrar. Antes solo se veía el resultado en la imagen.
- Desplazar y duplicar un taladro con avellanado dejan el volumen de la pieza sin cambios. Antes faltaba después hasta un milímetro cúbico.
- Si un paso divide una pieza en trozos sueltos, el informe lo dice — con el camino de vuelta mediante Ctrl+Z.

### Reconocimiento

- Una pared curva —el extremo de una pestaña, el fondo de una ranura— ahora se llama así. Antes ponía «Redondeo» con una arista que no existe. El radio se puede cambiar.
- Un agujero con resaltes en la pared, como el anillo de un cierre de bayoneta, es un agujero. Antes aparecía como un agujero alargado tan largo como ancho, y cualquier acción quitaba los resaltes.
- Una ranura con chaflán en el borde es una ranura; el chaflán forma parte de ella. Antes, en un marco aparecían 126 avellanados sueltos en el árbol.
- Una muesca o el extremo redondo de una lengüeta ya no es un taladro, y dos trozos de la misma pared redonda aparecen como uno en el árbol.
- Un trozo de cono sin borde propio se llama cara cónica. Se puede examinar, pero no editar por sí solo — y así lo dice cada fila.
- La pared interior de una rueda con radios no es un taladro, y un vaso con un agujero en el fondo no es un paso. Antes, «Desplazar» cortaba allí los radios.
- Los modelos grandes se reconocen hasta treinta veces más rápido: una pieza de relojería con 500 arcos tardaba dos minutos, ahora cuatro segundos.

### Vista y manejo

- Una casilla en un diálogo ahora conmuta en toda su fila — también al hacer clic en su texto. Antes solo respondía el pequeño cuadro, y «Abrir arriba» al ahuecar parecía no reaccionar.
- Cuando una vista previa no puede mostrar nada, la vista dice por qué — por ejemplo «Este plano no divide el objeto». Si el volumen no cambia, la banda lo dice; si tarda más, también.
- El paso «Dividir» empieza en el centro de la pieza en lugar de en su cara inferior. El número sigue siendo editable.
- Una herramienta que no puede hacer nada en esta pieza aparece en gris y dice por qué — «Cerrar superficie abierta» en una pieza cerrada, «Dividir en piezas» en una sola, «Rejilla» sin hueco.
- Asignar un filamento ya muestra el color en la vista previa; igualar y subdividir triángulos muestran la nueva malla con sus aristas. La barra espaciadora devuelve el antes.
- Ahuecar una pieza con agujeros en la envolvente dice ahora que la envolvente es el problema y ofrece «Reparar y reintentar» — en vez de avisar de que ningún cálculo funcionó.
- En el rasgo elegido aparece en gris lo que solo podría fallar ahí — «Girar elemento» en un taladro avellanado, por ejemplo — con el motivo. Y la vista previa avisa si al aplicar vendrá una pregunta.
- Un campo que no hace nada con la forma base elegida ya no aparece en gris en el diálogo — aparece con la forma que lo necesita. Un rectángulo muestra delante cuatro campos en vez de ocho.
- Con la pantalla al 150 o 200 por ciento, el ajuste, los tiradores y las marcas alcanzan lo mismo que al 100 por ciento. El tirador sale a tamaño completo y un clic tembloroso sigue siendo un clic.
- En un modelo grande la vista previa llega en menos de un segundo en vez de varios: Solidon la calcula de forma más basta y escribe «Vista previa aproximada». Aplicar sigue siendo exacto.
- El paso «Separar por una línea dibujada» empieza en el centro de la pieza y no en su cara inferior, como «Dividir». Antes la vista previa solo mostraba que el plano no separa nada.
- El paso «Alinear con una característica» le pide ahora que elija la segunda característica en lugar de explicarle una notación.
- El arranque ya no espera a la tarjeta gráfica: se busca mientras se construye la ventana. En equipos que tardaban en encontrarla, el programa se quedaba parado unos segundos.
- Lo que no es posible en un detalle aparece en gris con el motivo — la misma frase que la operación habría dicho tras el clic. Las frases son ahora más cortas.

### Archivos y exportación

- Un 3MF del slicer ahora se abre aunque sus colores no se puedan leer sin ambigüedad: el modelo llega en un solo color y el informe dice por qué. Antes, el archivo no se abría.
- Las caras pintadas en Bambu Studio, Orca y Elegoo llegan exactamente como se pintaron, incluso cuando un color atraviesa un triángulo. Antes eso contaba como «ambiguo».
- Un relieve de texto del slicer de Elegoo o de Bambu Studio en el archivo detenía la importación. Ahora el archivo se abre.
- Los modificadores y bloqueadores de soportes del slicer ya no aparecen como cuerpos, y un hueco («pieza negativa») se resta, como en el slicer.

### Bloques y ajustes

- Un bloque para agujeros — inserto térmico, alojamiento de tuerca, asiento de rodamiento, rosca, tornillo — se coloca directamente en el agujero elegido, no en el centro de la cara.
- Si arrastra un bloque por el asa en la vista, se mueve el bloque entero, aunque haya agarrado un borde del ojo de cerradura. Antes solo se desplazaba esa característica.
- Ganchos y agujeros de un bloque aparecen a la derecha como cantidad, no como «2,00 mm». Y tras «Cambiar medidas» el bloque sigue seleccionado, aunque tenga otras características.

## 0.4.1

### Construir y modificar

- Redondear y achaflanar funcionan ahora también en un modelo importado: se elige una arista en la vista y se indica el radio o la anchura. Antes solo servían en un cuerpo propio.
- Desplazar cara y ángulo de desmoldeo funcionan igualmente en un modelo importado, y allí se puede además cambiar o quitar un redondeo reconocido.
- Desplazar cara mueve la cara sobre la que se ha hecho clic. En una escalera los demás escalones se quedan donde están, en vez de desplazarse todos a la vez.
- El círculo de agujeros y la rejilla de agujeros son formas propias al dibujar, con sus medidas: número, círculo primitivo y diámetro. Antes eran seis círculos a mano.
- Novedad: «Añadir cordón», un listón redondo a lo largo de las aristas elegidas: por fuera como cordón, en un ángulo interior como cordón en ángulo. Un cuerpo exacto se convierte así en malla.
- Una arista se elige ahora en la vista: primer clic el cuerpo, después la arista. Longitud y los botones Redondear y Chaflán están a la derecha. Antes había que reconocerla en una lista.
- En un tubo, el borde interior y el exterior se redondean o achaflanan por separado. Antes ambos se llamaban igual, y la edición afectaba a uno de los dos.
- El ángulo de desmoldeo deja intacta la superficie de apoyo, aunque la pieza no esté a la altura cero. Antes, una pieza elevada se estrechaba también por abajo.
- Barrer a lo largo de una trayectoria empieza con la sección correcta y conserva los huecos del contorno: un anillo sigue siendo un tubo, en vez de salir deformado al principio y macizo por dentro.
- Un par de contrapiezas insertado cuenta como cambio: se guarda con el proyecto y se pregunta por él al cerrar. Antes podía perderse en silencio.
- El candado junto a una medida fijada en el editor de bocetos es ahora un símbolo dibujado con explicación. En algunos equipos aparecía allí un cuadradito.

### Taladrar y colocar

- Al colocar un taladro, una casilla lo convierte en ranura: usted indica la longitud y la dirección, y la vista previa muestra ambas.
- Un taladro que ya está en el modelo se alarga después hasta convertirlo en ranura; el diámetro se mantiene tal como se midió.
- La ranura se amplía en toda su longitud según la tolerancia del material. El recorrido que tiene un tornillo dentro sigue siendo el que usted indicó.
- Si una ranura sobresale del borde por un extremo, Solidon lo advierte, aunque su centro esté bien dentro del material.
- Una ranura figura en el árbol de objetos como ranura, con su anchura y su longitud, también en un modelo que usted haya abierto y que haya dibujado otra persona.
- Una ranura existente se puede alargar después, y su dirección se mantiene donde estaba.
- Un taladro o una ranura seleccionados se ajustan directamente en la vista con «Ajustar en la vista»: un asa para desplazar y girar, botones para estirar, cotas a bordes y centros.
- Solo «Aplicar», a la derecha, lo convierte en un paso; Escape lo descarta. Una ranura estirada muestra su longitud y conserva su forma cuando la desplaza con el asa.
- Un campo de coordenada vacío significa ahora «deja el taladro donde está». Así se puede colocar uno en el centro de la pieza, el único sitio al que antes no llegaba.
- Un taladro se desplaza con «Cambiar orificio» ahora también en el cuerpo exacto, y en la malla se mueve de verdad. Si se sale por el borde, Solidon dice que ya no es un agujero.
- La anchura de una ranura se cambia con «Cambiar orificio». El recorrido que tiene un tornillo dentro se mantiene.
- Si un taladro o una ranura atraviesa la pieza por completo, de modo que se parte en trozos, el informe lo dice, y no solo que el agujero sobresale del borde.

### Reconocimiento

- Un avellanado sobre un taladro se conserva también en una pieza con superficies redondeadas y curvas: antes se perdía ahí, y el taladro y su avellanado ya no podían desplazarse juntos.
- Una cavidad por completo dentro del material, sin salida, aparece en el árbol de objetos como bolsa de aire, con su volumen. Antes aparecía como un taladro que no existía.
- En un modelo muy curvado, Solidon dice ahora qué se ha medido, en vez de llamarlo un escaneo, y qué características se omiten en una superficie así.
- El reconocimiento de características en modelos grandes de forma orgánica es aproximadamente una cuarta parte más rápido. Encuentra lo mismo que antes.
- Si entre un taladro y la pared que lo rodea queda menos material del que aguanta el suyo, el informe lo dice, medido en la pieza terminada.
- El mapa de defectos de malla marca ahora también las caras que se atraviesan entre sí. Antes solo veía aristas abiertas y ramificadas y daba por sano un modelo así.
- El análisis por capas de una pieza con moleteado fino tarda ahora la mitad; los puntos señalados son los mismos que antes.
- Que un puente cuente como demasiado largo depende ahora de su boquilla: dos líneas de una boquilla de 0,4 son 0,84 mm, no un milímetro redondo. Cambios menores ya no salen en el chat como «+0,00 cm³».
- El reconocimiento de roscas necesita solo una fracción de la memoria y se puede cancelar.
- Si un cuerpo no se puede separar por una malla abierta, la reparación aparece como botón en el hallazgo.
- Si un corte no se puede tapar, Solidon dice que el modelo no está cerrado, y cómo seguir, en vez de señalar el corte.

### Rotular

- Una inscripción puede usar ahora ocho fuentes en lugar de tres, más negrita y cursiva. La negrita lleva trazos más gruesos con la misma altura y sigue siendo legible donde la normal se emborrona.
- Junto a las fuentes rectas hay ahora una redonda y una manuscrita, ambas en un solo estilo. Las ocho viajan con el programa, así que un proyecto se ve igual en todas partes.
- Si una fuente es demasiado fina para su boquilla, Solidon indica a partir de qué altura aguanta, en lugar de imprimirla y dejar que las letras se empasten.
- Los lados curvos de una letra, el arco de la D o el contorno de la o, aparecen ahora en el árbol de objetos como los rectos y aceptan su propio filamento. Antes faltaban por completo.

### Bloques y ajustes

- Un bloque del catálogo aparece de inmediato en la vista: sobre la cara seleccionada o encima del cuerpo, con líneas de cota y asa. Un clic lo coloca en otro sitio, «Aplicar» lo inserta.
- Si separa en piezas sueltas un cuerpo con un ajuste, Solidon pregunta a qué pieza se refiere ahora el ajuste, en lugar de mandarle a deshacer los pasos.
- El casquillo de inserción M2,5 recibe su agujero de montaje según la hoja de datos: 4,0 mm en lugar de 3,6. Un proyecto anterior con este casquillo avisa al abrirse de que la medida ha cambiado.
- El aviso de un brazo de gancho que se rompe cuenta con la dirección de impresión desfavorable: un brazo que flexiona a través de las capas aguanta menos, y eso figura ahora en la frase.
- El generador de variantes graba a cada pieza su valor en la cara superior. Si una pieza es demasiado pequeña para un número legible, el informe lo dice e indica el orden en la placa.

### Vista y manejo

- Las acciones para un cuerpo o característica seleccionados están a la derecha, en grupos plegables, con búsqueda. Los menús Objeto, Modificar y Preparar desaparecen; los atajos siguen.
- El clic derecho sobre un cuerpo o una cara muestra solo lo que existe únicamente allí: el paso detrás, el boceto sobre la cara, ocultar. El botón «Bloques» está en color de acento.
- Si la cadena se detiene en un paso, las acciones quedan bloqueadas y dicen por qué; intentarlo muestra las salidas del informe. Antes, el paso quedaba en silencio detrás, sin calcularse nunca.
- El selector de placas de la cabecera está junto al nombre de la impresora, ya no encima — también cuando las placas llegan recién con el proyecto abierto.
- El informe agrupa los mensajes iguales en una línea, con el número entre paréntesis delante. Un clic selecciona todas las piezas afectadas; una acción pregunta a cuáles aplicarse.
- La columna derecha con informe, chat y recorrido es algo más estrecha; el espacio va al modelo.
- Al medir, la vista pasa a proyección recta y vuelve después. En perspectiva se apunta al lado, cuanto más lejos está el tramo del centro de la imagen.
- Quien solo mira un modelo ya no recibe la pregunta de guardar al cerrar. A cambio, los archivos importados aparecen en «Abiertos recientemente».
- Si se empuja un cuerpo con el asa más allá del borde de la placa, Solidon lo devuelve a un sitio libre. Un valor escrito se ejecuta tal como se introduce.
- La elección de idioma en los ajustes tiene efecto de inmediato; las demás entradas se conservan y Cancelar restablece el idioma. Vale también en la configuración inicial, que un cambio ya no cierra.
- Tras un cuarto de hora de trabajo, Solidon pregunta una vez por versión por su comentario. Responderlo o cerrarlo: en esta versión la pregunta no vuelve.
- Si el ratón 3D está bloqueado, Solidon indica el camino para habilitarlo en vez de pasarlo por alto en silencio.
- El camino a la impresora se llama en el menú «Preparar la impresión …» en lugar de «Ajustes de impresión …». El diálogo de detrás es el mismo.
- La tecla Intro en un campo de medida a la derecha aplica el paso, y el tabulador recorre los campos de arriba abajo.
- La paleta de comandos preselecciona la mejor coincidencia, no la primera ejecutable. «Redond» e Intro creaban antes un prisma.
- Si arrastra un cuerpo con el ratón, se queda en el puntero también sobre el fondo vacío, en vez de detenerse y saltar en cuanto vuelve a haber algo debajo.
- También tras abrir un proyecto, el primer clic en el modelo ya no da tirones; la preparación se hace en cuanto los cuerpos están en su sitio.
- Los movimientos finos de la rueda —touchpad, ratón de alta resolución— ahora hacen zoom en vez de perderse.
- Volar con la tecla Ctrl pulsada termina en cuanto la suelta. Antes la vista seguía volando.
- Con una escala de pantalla alta acierta en las asas con la misma facilidad que al 100 %.
- Tras un cambio de hallazgo, los botones del informe aparecían un instante como ventanitas propias. Eso se acabó.
- El contorno de capa de una pieza en la segunda placa está sobre esa pieza, no junto a la primera.
- En la pantalla de inicio solo quedan los menús que allí hacen algo.
- Un segundo bloque del mismo tipo — otra tapa roscada, por ejemplo — recibe un número en vez de llamarse como el primero.

### Archivos y exportación

- Antes de escribir, la exportación muestra lo que ha encontrado el informe: una pared delgada, un ajuste incumplido. Usted decide si el archivo se escribe igualmente.
- Solidon recuerda carpeta, formato y esquema de nombres por proyecto. Si se generan varios archivos, el patrón de nombre está en el campo y se puede cambiar.
- Al leer un modelo, el progreso se mantiene hasta que el modelo está de verdad, y la indicación dice «Leyendo el modelo» en lugar de «Cargando proyecto». Cancelar sigue disponible todo ese tiempo.
- Una pregunta respondida sobre qué característica quiere decir un paso sigue respondida, también tras cerrar y volver a abrir el proyecto.
- Si el archivo vinculado de un proyecto no está accesible, el proyecto se guarda y se abre igualmente; el informe nombra la fuente. Si faltan permisos, Solidon lo dice en vez de darlo por dañado.

### Cama de impresión y entrega

- Si un cuerpo de piezas sueltas —un rótulo, por ejemplo— no cabe entero en ninguna cama, el informe ofrece separarlo y orientarlo enseguida: un clic y las piezas quedan en las placas.
- Abrir en el slicer entrega a ElegooSlicer, Orca y Bambu Studio todas las placas en un solo archivo: una ventana en lugar de una por placa.
- En separación, rotulación y textura el informe indica la cifra en la frase, donde antes había un marcador entre llaves.
- Un letrero al que asignó un filamento lo conserva al separarlo en letras. Antes llegaba al slicer en un segundo filamento gris, y el asignado quedaba al lado sin usar.
- Con varias placas, las piezas llegan ahora al slicer donde él tiene sus placas: en la cuadrícula que él mismo dispone. Antes, las letras de la tercera y cuarta placa quedaban fuera de todo.
- Si al laminar queda una bobina sin usar, Solidon lo dice con su nombre. Antes el slicer informaba de éxito y en la impresión faltaba un filamento.
- Si un slicer se cierra de golpe, Solidon lo dice así. Antes se decía que no había escrito ningún archivo de impresión.
- Creality Print se reconoce como slicer y se puede elegir en el diálogo de impresión, con sus impresoras, procesos y filamentos.
- El diálogo de impresión se abre al instante con el slicer elegido la última vez; la búsqueda de otros corre en segundo plano. Antes, el clic en Imprimir podía no mostrar nada durante diez segundos.
- La selección de slicer muestra todos los programas instalados, también un segundo Flatpak o un segundo AppImage. Antes faltaba el segundo de cada ubicación.
- Un filamento de un paquete de fabricante de PrusaSlicer llega a la entrega con sus propios valores, no con los del primer filamento del archivo.
- En la entrega como STL —a Cura, por ejemplo— Solidon dice que los ajustes por pieza no viajan, y nombra la propuesta para toda la placa, en lugar de afirmar que están aplicados.

### Filamentos y almacén

- El almacén de filamentos también se puede guardar en una memoria FAT32, un disco exFAT o un recurso compartido de red. Antes, allí fallaba cada guardado.
- Si el almacén no se puede leer, Solidon lo dice también en el selector de filamento, con el botón «Volver a intentarlo», en vez de una lista vacía.
- El consumo medido en el archivo de impresión cuenta también el material extruido sin trazo y no cuenta dos veces las retracciones. Si el slicer escribe la cantidad, vale su cifra.
- Quien al descontar el consumo elige «No registrar» no vuelve a ser preguntado por esa salida; sigue accesible en «Sin registrar».
- Si crea una bobina nueva mientras descuenta el consumo, las bobinas elegidas, las cantidades introducidas y los repartos se mantienen.
- El árbol de objetos muestra en cuerpo y cara solo los filamentos que están ahí de verdad: una cara con filamento propio lleva el suyo, no la lista de todo el cuerpo.
- Cancelar durante la búsqueda de perfiles de filamento hace efecto de inmediato.

### Chat e IA

- Antes de la primera petición a un generador de modelos, Solidon dice qué datos van allí.
- Si otro proceso ocupa la tarjeta gráfica, el chat espera de forma visible en vez de quedarse parado.

### Actualización, instalación y sistema

- Los paquetes para Mac están firmados y notarizados. El rodeo por «Privacidad y seguridad» → «Abrir igualmente» ya no hace falta.
- En «Apoyar Solidon» ahora se puede elegir GoFundMe junto a PayPal; solo su clic abre el navegador, y sin navegador se puede copiar la dirección.
- Si su código de compra está en una unidad cuyos permisos de archivo no se pueden establecer —FAT, recurso compartido de red—, sigue siendo legible. Antes allí se daba por inexistente.

## 0.4.0

### Construir y modificar

- Las contrapiezas, como un pasador y su taladro, se colocan en las dos piezas en un solo paso. Las medidas comunes se indican una vez y una sola deshacer retira la pareja.
- Unir dos contornos admite ahora dos dibujos propios: redondo abajo, angular arriba. Así se construye el adaptador de un tubo a un canal.
- Barrer a lo largo de una trayectoria sigue un recorrido dibujado con varias esquinas y arcos, y no solo un arco uniforme. En las esquinas vivas Solidon corta a inglete.
- El redondeo y el chaflán funcionan también en una sola arista. La elige en una lista que indica cada arista con su posición y su longitud.
- Un bloque llega a varios sitios en un solo paso: cuatro taladros reciben juntos sus casquillos y una sola deshacer retira los cuatro.
- Novedad: *Comprobar la trayectoria de montaje* lleva una pieza a su posición final e indica dónde choca por el camino, aunque las dos encajen al final.
- Cada bloque puede exportarse como código OpenSCAD, desde el catálogo o desde la línea de órdenes.
- El núcleo exacto taladra también en una cara inclinada, con avellanado y ensanche; los patrones y los montajes encajados se conservan.

### Taladrar y colocar

- Al colocar un taladro, la vista previa muestra el contorno de la boca en lugar de un cilindro semitransparente. El punto que importa queda despejado.
- La vista previa sigue al ratón con fluidez: la búsqueda de la cara bajo el puntero ya no se rehace en cada movimiento.
- Los campos de medida se apartan del punto donde nace el taladro, en lugar de quedar encima.
- Quien elige una operación que se coloca en el modelo empieza a colocar de inmediato; el botón previo desaparece.
- Tras aceptar las medidas, la profundidad se ajusta con el ratón. El modelo se vuelve translúcido y la vista gira de lado para que pueda mirar dentro del agujero.
- Al arrastrar, la profundidad encaja brevemente en los puntos con significado: la mitad del material y su cara posterior.
- El prisma, la esfera y los demás cuerpos básicos se mueven y giran ya en la vista previa, con el mismo tirador que un cuerpo terminado.
- Los cuerpos básicos tienen ángulo de giro: la dirección dice hacia dónde apunta el cuerpo y el ángulo, cómo queda girado alrededor de ella.
- Taladrar en un cilindro, una esfera o un toro ya no provoca en cada taladro el aviso de que sobresale del borde.
- Un taladro con avellanado se elimina por completo tras la confirmación, en lugar de dejar el avellanado sin vuelta atrás.

### Características y selección

- Un taladro seleccionado ofrece solo las acciones que hacen algo allí; antes aparecían también rotular y asignar filamento.
- Cada acción sobre una característica aparece una vez y no dos, y desaparece el encabezado de bloque sobre una única fila.
- En un avellanado existente vuelve a estar disponible *Avellanar*.
- En el árbol de objetos, las características del mismo tipo solo se agrupan si coincide también su medida. Diez redondeos con radios distintos vuelven a aparecer por separado.
- Un cuerpo con filamento asignado vuelve a mostrar su selección en la imagen, en vez de quedarse gris como los demás.
- Los campos de una característica llevan su nombre: el lector de pantalla dice a qué pertenece cada campo, en lugar de repetir seis veces campo giratorio, 0,00.

### Bloques y ajustes

- Sus propios bloques se abren de nuevo desde el catálogo para editarlos, aunque el proyecto del que salieron ya no exista.
- La escalera de tolerancias adopta la medida real del taladro sobre el que la abre, en lugar de un valor fijo de 6 mm.
- Los ganchos y las lengüetas elásticas calculan con el material y el recorrido del muelle, no con una regla aproximada. Solidon avisa del brazo que rompe al primer encaje.
- Los tres cuerpos de calibración nacen sin cuerpo auxiliar, y la escalera de tolerancias se imprime como dos listones numerados que se encajan entre sí.
- El aviso del muelle mide el brazo real, la bisagra de película se mueve y el sujetacables llega hasta la vista previa y la salida.
- Un bloque añade material de apoyo antes de cortar cuando hace falta; y su vista previa se asienta bien incluso sin soporte.
- Un bloque explica qué combinación de medidas no puede construir, en lugar de recortarlas en silencio.

### Filamentos y almacén

- Su existencia de filamento tiene sitio propio: un mosaico en la página de inicio y una estantería en lugar de una lista, con el nivel dibujado como bobinado en el carrete.
- Dos bobinas con el mismo nombre se distinguen. Cada una lleva su propio resto, y la empezada es la interesante.
- Al laminar y al entregar, Solidon pregunta si debe descontar el consumo. Tras laminar es la cantidad medida en el archivo de impresión; si no, una estimación.
- Cada apunte se puede deshacer, cada bobina lleva su historial y solo descuenta sin preguntar quien lo configura expresamente.
- Un filamento asignado se puede quitar de nuevo sin que las caras vecinas pierdan el suyo.
- Una cara pintada llega a Orca y a PrusaSlicer con su filamento, ya no sin él.
- Tras retirar un filamento, el perfil del fabricante ya no acaba en el filamento equivocado.
- En la estantería, la búsqueda y las acciones principales están juntas, y el lugar de almacenaje y la carga nominal figuran en el diálogo de la bobina.

### Imprimir y preparar

- Solidon encuentra lo que tiene Cura: impresoras, perfiles de proceso y filamentos que antes quedaban invisibles.
- De PrusaSlicer, Solidon adopta los filamentos cargados y la impresora configurada por última vez.
- Si su slicer no conoce siquiera la impresora, Solidon lo dice, en lugar de enviarle a una lista en la que no hay nada.
- Cambiar el nivel de calidad tarda segundos y no casi un minuto, y la ventana sigue utilizable mientras tanto.
- El asesoramiento sobre los ajustes de impresión mira todos los cuerpos de la placa y no solo la selección. Lo que un cuerpo necesita se conserva aunque el vecino no lo necesite.
- Calcula en segundo plano, nombra el cuerpo, muestra su avance y se puede cancelar.
- Un puente largo se valora por sus apoyos reales, y el ángulo de voladizo vale para la impresora, la boquilla, la altura de capa y el ancho de línea con los que se midió.
- La velocidad excesiva se limita en el tipo de trayectoria afectado, en lugar de calentar cada vez más la boquilla y la cama.
- Las propuestas descartadas siguen descartadas, y un cambio de filamento, escena, placa o calidad invalida de inmediato un resultado obsoleto.
- La separación al distribuir cuenta el borde de adherencia y la estructura de soporte: entre dos vecinos ambos cuentan dos veces.
- Las piezas se distribuyen en el centro de la cama, como hacen los slicers de al lado, y no en la esquina posterior izquierda.
- Orientar para imprimir vuelve a distribuir después las piezas giradas. Un cuerpo que se tumba ocupa más superficie y antes acababa dentro del vecino.
- La segunda selección de filamento bajo los perfiles del slicer ha desaparecido. Repetía el selector de filamento; obtener los valores del perfil es ahora un botón propio.
- Orientar para imprimir toma todos los cuerpos de la escena, no solo los marcados. Así toda la cama se desplaza después al centro en vez de que una pieza girada esquive a otra parada.

### Vista y manejo

- El puntero de ratón de Solidon se usa en toda la ventana y en cada diálogo, no solo en la vista 3D.
- Cambiar la variante en un diálogo de operación ya no cierra la aplicación.
- Un diálogo de operación abierto ya no sobrevive sin más a un cambio de proyecto.
- Los avisos largos ya no se cortan mientras queda sitio libre al lado.
- Desde la línea de órdenes no se podía llamar a *Asignar filamento*; ahora sí.
- El primer clic y el primer giro ya no se atascan: lo que la vista debe preparar para ellos ocurre ahora al arrancar.

### Actualización, instalación y sistema

- En *Novedades* figuran las tres últimas versiones. El historial completo de todas las versiones está en solidon3d.de y sigue disponible allí.

### Manual y sitio web

- Las imágenes de solidon3d.de muestran el modelo a todo lo ancho, no como una franja entre los paneles.
- El manual y el sitio web nombran todas las operaciones que existen, incluidos los nuevos editores de características.

## 0.3.5

### Vista

- La vista 3D dibuja con una nueva capa gráfica. Se dirige a la tarjeta gráfica mediante Direct3D 12, Vulkan o Metal y sigue fluida incluso con varios millones de triángulos.
- Los rebajes y las aristas destacan más: la vista oscurece los rincones, traza líneas de profundidad y acierta el punto al que apunta.
- Las aristas de los cuerpos se muestran como una fina malla sobre la superficie, y los rótulos se mantienen quietos en lugar de temblar al girar.
- Los nombres de las características ya no se superponen y sus marcas siguen visibles también en la sección.
- El indicador de ejes de abajo a la izquierda llena su campo en cualquier dirección de vista y sus letras se ven completas.
- Las vistas fijas giran la cámara alrededor del punto que está mirando. Su encuadre se mantiene en lugar de volver a toda la escena; para encuadrar sigue estando *Ajustar a la vista*.
- Al apuntar a través de una abertura a la cara que hay detrás se selecciona esa cara y no el borde de la abertura.
- Los modelos grandes se construyen más rápido, porque las aristas y las normales se calculan una sola vez por cuerpo.
- Si el equipo carece del soporte gráfico que necesita la vista, la aplicación indica los dos paquetes que hay que instalar.
- Si inclina la vista cerca de un eje, encaja ahí y conserva su giro, en vez de saltar a una posición fija.

### Acciones para la selección

- El informe de comprobación y el chat cierran a la derecha con su propio borde. Las acciones para la selección quedan debajo en una tarjeta propia, y entre ambas se ve el modelo.
- Qué acciones aparecen delante depende de la selección: con varios cuerpos Unir, Sustraer e Intersección; con uno solo Hacer un taladro, Vaciar y Separar.
- En un taladro seleccionado aparecen Avellanar y Cerrar un taladro; en una cara, Hacer un taladro, Cortar una cavidad y Desplazar cara.
- Un cuerpo seleccionado muestra allí mismo sus filamentos y permite cambiarlos.
- Un campo de búsqueda en la misma tarjeta encuentra el resto de operaciones; las características y las piezas siguen en sus propias áreas.
- La columna derecha es más ancha: las acciones para la selección caben enteras, en vez de apretarse en media anchura.

### Construir y modificar

- Unir, Sustraer y Cortar toman todos los cuerpos seleccionados a la vez, no exactamente dos.
- Redondear ya no tumba la aplicación cuando el radio es mayor que la pared que debe redondear.
- Un cuerpo del núcleo exacto sigue siendo exacto si solo lo mueve o lo gira. Redondear y aplicar chaflanes siguen siendo posibles después.
- La herramienta de taladrado sobresale solo en la boca del agujero y rechaza diámetros que superan la pieza muchas veces.
- Alinear a ras significa a ras con un ángulo, no con una única distancia entre puntos.
- Reducir triángulos se detiene en una resolución con nombre, y el relleno de celosía ya no inventa un interior que no existe.
- El editor de bocetos acierta arcos en el círculo completo, encuentra bordes de círculo, borra con Supr el elemento elegido y no deja Rehacer pendiente.
- La respuesta al modelar ya no declara sin efecto los cambios pequeños.
- Los interruptores de una operación que están activos de origen ahora también se pueden desactivar desde la línea de órdenes.
- Un error dentro de una operación indica su causa: en el registro, en la línea que la detuvo y en el informe de error.
- Las entradas rechazadas en colocación, almacén de mallas y recetas llegan con una propuesta de acción en lugar de un error desnudo.
- Las piezas explican qué combinaciones de parámetros no construyen, en lugar de recortar medidas en silencio.
- Un número inadecuado de cuerpos seleccionados se avisa antes del cálculo, en lugar de omitir una entrada sin que se note.
- Colocar sobre una superficie solo modifica el documento al aceptarlo; una vista previa descartada no deja nada atrás.
- Las letras y las cifras se quedan en el campo de entrada: las teclas de navegación actúan solo cuando no está escribiendo allí.
- Separar en piezas sueltas convierte varios cuerpos sueltos de un archivo en un objeto cada uno: lo que no se toca no es una sola pieza.

### Características

- Un escaneo importado ya no trae cúpulas ni casquillos inventados; hasta ahora surgían por centenares de superficies redondeadas suavemente.
- Varias roscas en una placa se nombran por separado en lugar de reunirse en una sola característica.
- Esfera, toro y cono declaran su curvatura, los centros de cilindro coinciden con sus anillos finales y los pasos de rosca siguen el eje.
- El panel de características ofrece ajustes solo cuando hay un segundo cuerpo seleccionado y conoce cada grupo del núcleo.
- Los ajustes automáticos de corte ya no reparten dos veces el mismo nombre.
- La detección de características llega al mismo resultado más rápido en mallas complejas.

### Imprimir y preparar

- La búsqueda de orientación juzga en dos etapas: doscientas posiciones a partir de las normales, nueve de ellas en el análisis por capas.
- Su barra de progreso llega hasta el final aunque no hubiera nada que cortar.
- El programa de laminado recibe el mundo de la impresora y no el de Solidon, y un perfil propio conserva su base del fabricante.
- Los perfiles de laminado propios van delante del perfil del fabricante con el mismo nombre, y un AppImage encuentra su inventario.
- La limpieza posterior a la importación conserva las asignaciones de filamento.
- La impresora pertenece al proyecto y se cambia tanto en la cabecera como en el diálogo de impresión; los filamentos asignados, los colores y sus propios valores de impresión se conservan.
- Cada cuerpo lleva su filamento en el árbol de objetos: un campo de color delante del nombre y un clic para asignar otro.
- Varias bobinas del mismo tipo de material siguen distinguiéndose por nombre y color.
- Las operaciones correspondientes se llaman por lo que hacen: *Asignar filamento* y *Filamento en una cara* en vez de *Colorear pieza* y *Colorear cara*.
- La entrega al slicer resuelve cada bobina según su propio tipo de material; sus propios valores de impresión mantienen la prioridad.
- Si el mapa de soportes tarda demasiado, el cálculo termina con una explicación y ofrece reducir los triángulos.
- El diálogo de impresión sigue siendo plenamente utilizable también en ventanas estrechas.
- Orientar para imprimir alinea todos los cuerpos seleccionados, no solo el primero.

### Archivos y proyectos

- Un 3MF con muchos niveles de duplicación se rechaza antes de que 432 bytes se conviertan en mil cuerpos.
- Un archivo de proyecto pequeño ya no reclama gigabytes de memoria.
- Un archivo GLB en milímetros llega en milímetros y no como metros.
- Un guardado fallido ya no se lleva la última copia de seguridad, y cancelar cancela de verdad la importación.
- Un error tardío al leer ya no borra la fuente del siguiente proyecto.
- Si no se puede crear la carpeta de caché, el resultado ya calculado se mantiene.
- Un conjunto de variantes incompleto ya no se exporta en silencio.
- El boceto descartado se recupera con Deshacer, y un segundo objeto del historial ya no deja un Rehacer caduco.
- Dos informes de error del mismo segundo ya no se sobrescriben.
- Las entradas elegidas de forma explícita sobreviven a guardar y volver a abrir, en lugar de ser sustituidas por un valor predeterminado.
- Cancelar termina también el cálculo que sigue corriendo detrás de una variante.

### Chat e IA

- Una herramienta adicional con un campo mal tipado ya no interrumpe toda la serie del agente.
- Para las variantes de boceto el agente indica solo rutas de menú que existen.
- En la generación de imágenes los pesos llegan completos o no llegan, y un solo valor en el campo de estructura ya no provoca una generación no pedida.
- Un modelo local se mide también cuando responde por HTTPS en un puerto propio.
- El aviso sobre la participación de la IA rige solo con constancia escrita, y un cambio de idioma ya no termina el mando a distancia.
- La instalación de ComfyUI adopta los pesos de modelo que ya están completos, en lugar de descargarlos otra vez.

### Actualización, instalación y sistema

- La versión mínima es ahora macOS 13, igual en paquete, instalador y sitio web.
- Trece bibliotecas están en sus versiones estables más recientes, y el núcleo exacto habla OpenCASCADE 8.
- Un paquete sin ancla de confianza en el sistema trae su propio juego, en cualquier plataforma.
- Una descarga ya no se interrumpe tras un tiempo total fijo, y una respuesta a goteo respeta el plazo prometido.
- Dentro del Flatpak la aplicación encuentra el gestor de paquetes del equipo.
- En Linux y macOS una interrupción ya no termina solo en el proceso padre.
- La entrada de menú de Linux encuentra el lanzador incluso sin entrada en la ruta de búsqueda.
- En el Mac el diálogo de actualización dice que Solidon vuelve por sí mismo tras el instalador.
- En el Mac el ratón 3D lee a través del controlador del fabricante en lugar de esperar a su lado.
- La pantalla de inicio reconoce el sistema antes de la primera imagen, y la tabla de requisitos ya no se corta.
- Un adjunto rechazado ya no cuenta como ausente para el mensaje de vuelta.
- El selector de filamentos permanece en la bobina correcta tras una cancelación y muestra también la octava.
- Un correo de soporte abierto a mano lleva asunto y texto legibles también dentro de Flatpak; cancelar deja el informe en su sitio.

### Manual y sitio web

- El manual y las capturas muestran la interfaz renovada en los seis idiomas.
- Los dibujos del manual mantienen el contraste del texto también en sus notas al margen.
- La ventana del manual carga solo sus propias figuras y ninguna imagen externa.
- El sitio web dice en un solo lugar qué sale de su equipo.
- La introducción ya no afirma que un agujero esté cerrado cuando Deshacer solo devuelve el diámetro.

## 0.3.4

### Editar características detectadas

- Un taladro y su avellanado vinculado se desplazan ahora juntos, sin importar cuál de los dos se seleccione. El panel de características indica la vinculación antes del cambio.
- Al modificar un taladro, su avellanado permanece asignado debajo de él en el árbol de objetos y también se puede ajustar directamente.
- El panel de características agrupa las acciones no disponibles iguales e indica con claridad los grupos de campos afectados.

### Reconocimiento de características

- Las roscas de los modelos importados se reconocen con mayor fiabilidad; los conos, salientes y esferas incorrectos que aparecen en ellas ya no se muestran como características independientes.
- Las uniones estrechas entre formas ensambladas ya no generan una gran cantidad de características incorrectas.
- El reconocimiento de características es notablemente más rápido en modelos grandes y detallados.

### Mapas de análisis

- Los mapas de análisis están disponibles para más modelos grandes.
- Si un mapa de análisis es demasiado grande para un modelo, el aviso ofrece directamente *Reducir triángulos*.
- El análisis de la necesidad de soportes es considerablemente más rápido en modelos grandes.

## 0.3.3

### Vista y selección

- El primer clic selecciona la pieza, el segundo el taladro que hay debajo, y un clic al lado anula la selección; el control elegido se mantiene en todo momento.
- Al girar, el horizonte permanece horizontal: tras un gesto la vista queda tan recta como antes, en cada uno de los cinco controles.
- El control y el tema elegidos en los ajustes aparecen también marcados en el menú *Vista*.
- Varios cuerpos seleccionados siguen seleccionados tras un nuevo cálculo, y un arrastre los mueve juntos.

### Trabajo en el proyecto

- Un proyecto se puede guardar también cuando una característica lleva un aviso.
- Cambiar entre dos mapas de análisis del mismo cuerpo muestra al instante lo que ya está calculado.
- Un proyecto nuevo empieza sin restos de una vista previa que seguía abierta al cambiar.
- Mediante el control remoto, *Deshacer* retira exactamente el paso indicado y no el último.

## 0.3.2

### Editar características reconocidas

- Al desplazar, girar o quitar un taladro no queda material en su sitio anterior, tampoco en piezas con ranura o hueco interior.
- El comando *Cerrar un taladro* rellena ahora exactamente el taladro: el tapón ya no sobresale hacia una ranura ni engrosa la pieza.
- Una cuenca esférica se reconoce como superficie esférica y no como avellanado, también en modelos de malla fina, y ofrece así las acciones que le corresponden.
- Un taladro duplicado recibe una identidad propia y no la de uno borrado antes, de modo que un ajuste sigue señalando la característica que designa.
- También al girar, un taladro pasante avisa si en la nueva orientación ya no atraviesa.
- Una característica recién creada aparece al final del árbol de objetos y no entre las anteriores.
### Visualización y selección

- La vista previa desaparece en cuanto se aplica el cambio; hasta ahora el cuerpo de comparación con la banda «aún no aplicado» quedaba sobre el taladro terminado.
- La barra espaciadora vuelve a alternar entre antes y después solo donde hay una vista previa, y ya no en toda la aplicación.
- Un taladro ya no se ilumina en el color de selección cuando no hay nada seleccionado.
- El arco de giro, la sombra, las marcas de arrastre y el anillo del pincel desaparecen con la acción a la que pertenecen, también al cambiar de herramienta o cerrar.
- Una medida permanece en su pieza, aunque la vista cambie a otra placa de impresión o a todas.
### Impresión y memoria

- Si no cabe todo en una placa, se crean tantas placas como haga falta; hasta ahora el resto quedaba junto a la mesa, donde no se puede imprimir.
- La memoria de características de modelos grandes se mantiene acotada; hasta ahora podía ocupar hasta un gigabyte.
## 0.3.1

### Editar características reconocidas

- Las características reconocidas se pueden mover, girar, duplicar y quitar: un taladro, una espiga o una cúpula; la cúpula sin girar, porque no tiene orientación.
- Cambiar el tamaño funciona ahora también en una espiga o una cúpula; hasta ahora solo en un taladro.
- Los valores medidos ya están en los campos: se acaba el rodeo de tapar y volver a taladrar con cifras copiadas a mano.
- Un taladro desplazado sigue siendo el mismo taladro: todo ajuste que lo señala conserva su referencia.
- Cuando una acción no tiene sentido para una característica, sigue visible y explica en una frase por qué, en lugar de faltar en silencio.
- Un panel *Característica* se abre a la derecha en cuanto se pulsa la primera característica y muestra lo medido allí; se puede desacoplar, cerrar y recuperar desde *Vista*.
- Cada cifra es modificable: posición, diámetro, profundidad y eje se fijan en el propio campo, sin diálogo intermedio.
- Una cifra modificada aparece como vista previa en la imagen antes de aplicarse.
- Una casilla *Aplicar a todos los del mismo tipo* cambia toda una hilera de taladros de una vez, con un único paso para deshacer.
- Dos características marcadas indican su distancia de centro a centro y por eje.
- Un taladro indica su medida normalizada — «mide 5,19 mm, el agujero de paso para M5» — y también avisa cuando ninguna encaja.
- Un segundo taladro igual al primero se obtiene duplicando, en vez de teclear de nuevo las medidas.
- La tecla Supr quita la característica seleccionada y ya no el cuerpo completo.
- Un doble clic en una fila de la lista de objetos abre lo que la modifica: el diálogo correspondiente en una característica reconocida, el paso con sus medidas en una creada.
- Un taladro pasante que tras el desplazamiento ya no atraviesa lo indica, y un avellanado que cerraría su taladro no se puede desplazar.
- Reducir un taladro hasta que deja de ser uno da una explicación en vez de pedir un informe de error.
- En una cara, un botón lleva al catálogo de bloques en vez de mostrar filas que solo dicen lo que allí no funciona.
### Mover, girar y seleccionar

- El asa de movimiento se sitúa en lo seleccionado: en un taladro, en su boca, y no en el centro de la pieza.
- Se mueve lo que está seleccionado: con un taladro marcado, el asa y la barra desplazan el taladro, no la pieza entera.
- Al arrastrar, una vista previa transparente muestra hacia dónde va el taladro y una copia pálida de dónde viene.
- La sombra acompaña el desplazamiento y muestra así la altura sobre la placa.
- Al girar, un arco muestra cuánto se ha girado y que el ángulo se ajusta a múltiplos de 45 grados.
- Los giros pequeños llegan: hasta ahora un ajuste angular invisible se tragaba todo movimiento menor que su paso.
- En una cara, la barra de movimiento solo ofrece lo posible allí e indica el motivo en el botón, no en un mensaje tras pulsar.
- El botón *Aplicar* desaparece: se aplica con Intro en el campo o arrastrando el asa, y exactamente una vez, no dos.
- Una pieza desplazada ya no salta un instante a su sitio anterior al soltarla.
- Un clic derecho en la lista de objetos acierta la fila señalada, no las dos de encima.
### Vista y árbol de objetos

- La vista tiene un control propio, y es el nuevo predeterminado: arrastrar con el izquierdo desplaza, con el derecho gira, la rueda pulsada inclina y la rueda acerca.
- Con W, A, S y D se vuela por la escena, y Q y E inclinan; el vuelo atraviesa una pieza, mientras que el zoom se detiene delante.
- Quien esté acostumbrado a otro control lo elige en los ajustes: siguen los esquemas de Cura, de Bambu Studio, Orca y PrusaSlicer, de un CAD y de Blender.
- La entrada *Ajustar a la vista* encuadra la pieza pulsada; sin selección, toda la escena como hasta ahora.
- Una pieza bajo la placa de impresión se ve: ahora es la placa la que es transparente, no el modelo.
- Los cuerpos semitransparentes se dibujan en el orden de profundidad correcto, sea cual sea el orden en que se crearon.
- La vista ajustada se mantiene, en vez de volver atrás en el paso siguiente.
- La selección y los cambios en la vista 3D transcurren con transiciones suaves en lugar de saltos bruscos.
- A partir de cuatro características con el mismo nombre, el árbol de objetos muestra una fila desplegable con su número en vez de cientos de filas.
- Solo se muestra lo que una impresora puede fabricar: las características de menos de medio milímetro desaparecen; en un soporte de manguera, 296 de 1130.
- Los redondeos con radio cero desaparecen así del árbol de objetos.
- Un clic en un cuerpo ya no cuesta espera; en un conjunto de 63 MB eran tres cuartos de segundo.
- Cambiar la representación y reconstruir la imagen de modelos grandes cuesta un tercio del tiempo anterior.
### Dibujo y entrada precisa

- La longitud y la anchura de un dibujo seleccionado son editables; el dibujo sigue la cifra modificada junto con sus cotas.
- Una cota mal puesta se puede deshacer por sí sola, y no solo junto con todas las demás.
- Tras extruir un croquis, el diálogo vuelve a ofrecer también el camino para restarlo.
- Una cota escrita vale tal como se escribió: 0,1 ya no se convierte en 0,166667.
- El diálogo de unidades pide milímetros y muestra una cifra en lugar de «nan».
- El campo del chaflán se llama anchura, y su mensaje habla también de la anchura y no del radio.
- Un clic en la ranura de un control deslizante lo coloca en el punto pulsado, no una página más allá.
- Al medir, el punto de destino se ancla en los bordes del modelo y no en líneas que no están en la imagen.
### Apertura, guardado y archivos de intercambio

- El primer modelo de un proyecto queda centrado en la placa de impresión y no donde lo deja su archivo; los siguientes conservan su posición.
- Un archivo defectuoso se rechaza al abrirlo, en vez de aceptarse y acabar en el proyecto al guardar.
- El rechazo indica el motivo — vacío, truncado, no es STL, no es 3MF, sin triángulos, con coordenadas inservibles — y ofrece *Elegir otro archivo*.
- La descarga interrumpida de un archivo de modelo se reconoce como tal.
- Los archivos de más de ocho megabytes se leen con indicador de carga y progreso, en vez de dejar la ventana catorce segundos sin respuesta.
- Un nombre de archivo llega al disco tal como se escribió, con espacios, acentos, paréntesis y signo más.
- Un modelo se puede guardar como 3MF sin los valores de impresión de Solidon, para que llegue sin cambios al slicer.
- Donde STEP no es posible con una malla, el rechazo ofrece directamente *Guardar como 3MF*.
- Un modelo con una malla demasiado fina recibe *Reducir triángulos* como botón en el hallazgo, no solo como consejo en el texto.
- Un hallazgo que afecta a varios cuerpos se puede resolver para todos a la vez, eligiendo cuáles, con un solo Ctrl+Z para toda la acción.
- El comando *Auto Split* avisa cuando un corte deja una superficie abierta, y un corte por un cuerpo editable ya no deja la escena vacía.
- Escalar una pieza por debajo del límite de la máquina genera un hallazgo; hasta ahora solo lo había para demasiado grande.
- Los bloques propios llevan el mismo aviso que los incluidos.
### Impresión, slicer y filamento

- El diálogo de impresión muestra los perfiles que corresponden a la impresora ajustada, en vez de un fondo de 1001 entradas.
- Con una Elegoo Centauri Carbon son cuatro, y el correcto viene preseleccionado.
- Cambiar la impresora del proyecto arrastra volumen de impresión, boquilla y código de inicio: un proyecto Prusa ya no recibe la máquina de la Elegoo.
- El slicer recibe los datos de la máquina y devuelve un archivo de impresión, en vez de abortar con «no compatible con la impresora».
- Si el slicer está en otra impresora que el proyecto, Solidon lo dice en vez de aceptarlo en silencio.
- El aviso de perfil ausente indica de qué impresora se trata.
- La lista de filamentos permanece vacía mientras no se elija un perfil de máquina e indica ese motivo, en vez de ofrecer 5962 bobinas.
- La selección de filamento se puede filtrar por fabricante, material y los valores que aporta un perfil.
- Donde Solidon pone un borde, indica qué pieza lo necesita y por qué.
- Lo que la máquina no puede hacer se indica en todos los campos afectados, y no solo en uno.
- Las recomendaciones del informe que el slicer no acepta ya no prometen ningún efecto.
- Los objetos de materiales distintos van a placas separadas: la junta de TPU ya no en la placa de la carcasa de PETG.
- El aviso de impresión da un consejo en vez de remitir a números del contrato de licencia.
### Mensajes, botones e información

- Los botones bloqueados indican ahora en el propio botón lo que les falta: con el ratón, con el teclado y para un lector de pantalla.
- Entre ellos, *Laminar* y *Abrir en el slicer* sin slicer configurado, *Insertar* en el catálogo de bloques y *Generar* en el diálogo de modelo.
- Los rechazos no terminan solo con la frase, sino con la salida.
- Un error inesperado se explica en el idioma ajustado, en vez de recitar un texto interno en inglés.
- El diálogo Acerca de indica quién está detrás de Solidon y quién responde a los comentarios.
- Un enlace a una versión anterior lleva a la actual en lugar de a una página de error.
- La instalación en Windows llega al final también en equipos donde antes abortaba con «archivo defectuoso»; a cambio el archivo de instalación es 23 megabytes mayor.
### Chat y compatibilidad con modelos

- Si una referencia a una característica es ambigua, el chat se detiene, resalta los candidatos en la imagen y pregunta, indicando el cuerpo al que pertenece cada uno.
- Cuando el chat distribuye objetos en placas de impresión, el resultado se ve después en la imagen.
- Un hallazgo sobre un conjunto señala el cuerpo del que se trata y lleva su acción; donde no hay ninguna, es un simple aviso.
- El chat conoce las nuevas acciones sobre características reconocidas y las ejecuta cuando se le pide.
## 0.3.0

### Primeros pasos y orientación

- Cuatro introducciones guiadas explican las vías principales desde el primer diseño hasta un resultado imprimible.
- La pantalla de inicio aprovecha por completo las ventanas pequeñas y estrechas, sin tarjetas recortadas ni contenido oculto.
- Los proyectos recientes aparecen antes de los recorridos introductorios y son más rápidos de abrir.
- La pantalla de inicio ya no mueve la selección sin pedirlo y se puede manejar por completo con ratón y teclado.
- Las entradas *Nuevo*, *Abrir* y *Ejemplos* están mejor ordenadas y explican adónde conducen antes de abrirse.
- Los comentarios y el apoyo voluntario están en la pantalla de inicio y funcionan con teclado y tecnologías de asistencia.
- El chat sigue siendo utilizable incluso con poca altura de ventana: la entrada permanece fija abajo y el contenido se desplaza.
- La barra de herramientas superior permanece visible en proyectos abiertos y ventanas estrechas, sin salirse del área de trabajo.
- Un nuevo ejemplo de dibujo conduce directamente al flujo de bocetos y complementa los proyectos de ejemplo existentes.
- La pantalla de inicio tiene un botón *Abrir modelo …*, y la zona para soltar archivos también se puede pulsar.
### Interfaz y manejo

- Los menús tienen encabezados claramente visibles y columnas de iconos alineadas de forma uniforme.
- El resumen de comandos alinea bien los atajos y las explicaciones para recorrer con rapidez las entradas largas.
- Los diálogos extensos usan columnas y anchos de campo uniformes.
- La antigua página conjunta de adherencia, retracción y filamento se divide en áreas de ajustes más pequeñas y bien nombradas.
- Los 56 ajustes de impresión se pueden buscar por sus nombres visibles en español.
- La búsqueda también entiende 146 términos habituales de los slicers, entre ellos *perimeters* y *wall loops*.
- Los campos numéricos responden bien a las flechas, los pasos y el redondeo, sin cambiar valores de forma inesperada.
- Los controles deslizantes tienen un aspecto uniforme con un tirador fácil de agarrar.
- El color de acento queda reservado al botón principal; la herramienta activa se distingue por su borde y los controles inactivos pasan visualmente a segundo plano.
- Los cálculos muy breves no muestran parpadeos, los medios usan un cursor de espera y los largos añaden progreso y cancelación.
- Las indicaciones de las herramientas ocupan una línea cuando hay espacio y se ajustan de forma controlada en ventanas estrechas.
- Las miniaturas del árbol de objetos son lo bastante grandes para reconocer las formas.
- La lista de filamentos se desplaza por separado; *Añadir filamento* y *Valores de impresión* siguen accesibles con muchas bobinas.
- Los avisos y errores se leen bien sin transmitir su significado solo mediante el color del texto.
- Los campos de selección desactivados se distinguen claramente de los campos seleccionados y activos.
- Un ratón 3D (SpaceMouse) mueve el modelo en los seis ejes en cuanto se conecta; un botón del dispositivo encuadra todo.
- La placa de impresión se oculta con un clic o Ctrl+Mayús+D y permanece así hasta que vuelva a hacer falta.
### Dibujo y entrada precisa

- Los círculos se introducen por su diámetro, de modo que un agujero M3 se puede crear directamente con 3,2 mm.
- Una restricción de diámetro sigue siendo una expresión editable después de resolver, guardar y volver a abrir.
- Las medidas se editan directamente con un doble clic, sin el largo recorrido de selección anterior.
- La posición X, Y y Z, el ángulo y la escala se pueden introducir directamente en la barra de movimiento.
- Una entrada exacta crea el mismo paso reversible que un movimiento con el ratón.
- Varios cuerpos seleccionados usan un centro común al girarlos y escalarlos con valores exactos.
- Escape retrocede exactamente un nivel al dibujar: línea actual, herramienta actual y, después, todo el boceto.
- Rehacer funciona ahora también mientras hay un boceto abierto.
- Un boceto vacío muestra una indicación en la que se puede hacer clic y que abre las formas básicas listas.
- El botón de las formas básicas se llama como lo que hace un clic. Las demás formas están tras la flecha contigua.
- La herramienta de sección se abre dentro del cuerpo en lugar de en una vista vacía fuera del modelo.
- Las vistas frontal, lateral, superior y opuesta se ajustan de forma fiable a los seis ejes.
- El asa de arrastre sigue visible con la cámara plana o inclinada y muestra una medida útil.
- La herramienta de medición termina cada medida con una respuesta visible, en lugar de parecer que pierde el resultado.
- Al levantar, la medida aparece junto al contorno de alambre, y tras soltar todos los valores siguen editables en el diálogo.
- Las medidas al dibujar siguen la cuadrícula, no el puntero: se ve la medida que realmente se obtiene.
- Las medidas de círculo se pueden cambiar entre diámetro y radio en el propio campo; la elección vale en bocetos y diálogos y se recuerda.
- Un círculo con centro fijo y diámetro acotado se considera completamente determinado; la línea de estado ya no avisa de una medida que falta.
### Vista, historial y edición de formas

- Se pueden mover conjuntamente varios cuerpos seleccionados.
- Varios cuerpos seleccionados giran alrededor de un centro común y conservan sus distancias.
- Después de girarlos, los cuerpos pueden volver a colocarse bien sobre la placa en el mismo paso.
- Los movimientos consecutivos del mismo cuerpo se agrupan en un paso comprensible del historial.
- Las acciones relacionadas aparecen como una entrada desplegable, sin saturar el historial con líneas individuales.
- Una acción continua se puede revertir por completo con una sola orden de Deshacer.
- Las entradas del historial muestran su tipo y un número de paso inequívoco.
- Los modelos descargados e importados se pueden cortar de inmediato.
- Al seleccionar un hallazgo, Solidon lleva al lugar, al cuerpo o al paso del historial correspondiente.
- Al saltar a un hallazgo, la cámara encuadra el destino en lugar de acabar en un primer plano gris.
- Las caras con nombre y los hallazgos se mueven con su cuerpo al organizarlo y colocarlo.
- El modelado con pincel avisa si los trazos no alcanzan el modelo o no producen un cambio imprimible.
- Un texto en una pared lateral queda horizontal y derecho en lugar de en un ángulo cualquiera; en la cara superior e inferior sigue mandando el ángulo indicado.
- Si un rótulo queda dentro del cuerpo en vez de sobre él, la operación lo dice y señala el camino: hacer clic en la cara donde debe ir el texto.
- Los cuerpos ahuecados mantienen el grosor de pared deseado también en caras inclinadas y curvas.
- Un agujero ampliado a propósito conserva su nombre y sus ajustes en lugar de contar como perdido en el informe.
- Las esferas con muchísimos segmentos siguen siendo una malla manejable en lugar de veinte millones de triángulos.

### Bloques propios y archivos de intercambio

- Los bloques propios se pueden guardar como archivos locales .solidon-part y volver a añadir al catálogo.
- Los archivos de bloque se pueden abrir, arrastrar e importar mediante la asociación de archivos del sistema operativo.
- El nombre y la extensión muestran de inmediato que un archivo pertenece a Solidon.
- La importación, el intercambio y la biblioteca local usan textos completos de interfaz en los seis idiomas.
- Antes de guardarlo, un bloque propio se puede construir con varios pasos y valores editables.
- Al compartirlo se puede elegir entre uso libre, atribución o atribución con las mismas condiciones.
- Si se da un nombre propio a un bloque, este prevalece sobre el nombre que traiga el archivo.
- El origen y las condiciones de uso siguen siendo reconocibles al intercambiar un bloque.
- Los ganchos de encaje, ojales de bisagra, ganchos para panel y pies tienen transiciones más robustas sin superficies internas cerradas.
- Las tarjetas del catálogo conservan su posición y la cara seleccionada cuando terminan de cargar sus vistas previas.
- La escalera de tolerancias rotula cada escalón con su propio número.
- Los archivos GLB exportados aparecen de pie en otros programas en lugar de tumbados.

### División, impresión y filamento

- La división automática prefiere uniones resistentes y evita elegir el punto débil más fino posible.
- Para cada unión se elige por separado el conector adecuado y se guarda como una forma concreta.
- Las indicaciones sobre uniones pegadas permanecen asociadas a la unión elegida.
- La división automática responde de forma reproducible a nuevos requisitos y se puede cancelar durante el cálculo.
- La búsqueda de orientación solo comprueba posiciones distintas y respeta el tiempo previsto incluso con cuerpos exigentes.
- Los archivos 3MF grandes se reconocen y procesan más rápido sin cambiar el archivo resultante.
- El material, el ajuste y las tolerancias siguen la bobina realmente elegida o la ranura ocupada de la impresora.
- La cabecera muestra el material realmente usado y ya no ofrece una segunda selección contradictoria.
- Cuando está desactivado, *Guardar archivo de impresión* explica que el archivo solo se crea al laminar.
- Las reparaciones ya completadas en el mismo flujo de trabajo no vuelven a aparecer como recomendaciones pendientes.
- Los taladros para pasadores se abren en la división con un chaflán de entrada, y el resalte de un bolsillo de clip queda en la costura.
- Un diámetro de pasador elegido a mano tiene que caber en la costura; si por ello queda más fino, el informe lo dice.

### Informe, estabilidad, plataformas e idiomas
- En Linux con una sesión Wayland, Solidon arranca y muestra la vista 3D; si al sistema le falta una biblioteca, la aplicación arranca igualmente e indica cuál falta.

- Los hallazgos similares se agrupan sin perder la relación con los cuerpos y lugares afectados.
- Los números y medidas del informe tienen nombres completos en vez de valores sueltos incomprensibles.
- Si una reparación falla, se restaura por completo el cuerpo original sin modificar.
- Una malla importada cerrada ya no se abre por eliminar demasiado pronto un triángulo problemático.
- Los botones de acción del informe ya no mantienen en memoria una ventana que ya se ha cerrado.
- Los bloques incluidos y la activación se cargan al iniciar sin bloquearse entre sí.
- La vista 3D se cierra antes que la ventana; así, las ventanas de Windows, Linux y macOS se cierran con mayor fiabilidad.
- En Windows 11 la barra de título sigue el esquema de colores de la aplicación; las demás plataformas no cambian.
- Los botones estándar como Abrir, Guardar y Cancelar cambian de idioma al instante, sin reiniciar.
- Los nombres creados automáticamente para cuerpos y bloques cambian bien de idioma incluso después de usar contenido en caché.
- Las traducciones y los valores del informe están al mismo nivel en alemán, inglés, español, francés, italiano y portugués.
- Una pieza sin observaciones ofrece en el informe directamente el botón *Entregar al slicer …*.
- Cada mapa de análisis explica al señalarlo qué muestra, y la pregunta por la unidad al importar nombra las unidades con palabras.
- Una pieza que llena la cama de impresión se lee en milímetros sin preguntar.
- Los nervios finos junto a placas gruesas se reconocen como punto fino, y los puentes se miden en su anchura realmente libre.
- A una pieza que se apoya sobre sí misma no se le recomiendan soportes desde la cama.
- Las recomendaciones de impresión comprueban todas las velocidades, calculan la primera capa con sus propias medidas y avisan de una cama o cámara demasiado fría para el material.
- Las orejetas apiladas conservan cada una su taladro, y los arañazos finos no cuentan ni como taladro ni como espiga.
### Chat y compatibilidad con modelos

- El chat se abre con una explicación concreta de su finalidad, no con un área vacía ni términos técnicos de modelos.
- Los contadores técnicos de tokens se han retirado de la interfaz normal para clientes.
- Los avisos idénticos sobre detalles de forma perdidos llegan al asistente contados en lugar de uno por uno.
- El diálogo Generar convierte texto o una imagen en un modelo mediante ComfyUI local y lo incorpora a la misma escena editable.
- El flujo TripoSG incluido crea un GLB que después se repara, se escala y se comprueba para la impresión automáticamente.
- Ollama local y ComfyUI local calculan uno tras otro para no ocupar la tarjeta gráfica al mismo tiempo.
- Tras una propuesta del agente o una generación 3D, Solidon descarga los modelos locales y libera la memoria gráfica.
- Al cancelar, Solidon elimina solo su propia tarea de ComfyUI; las demás tareas que se ejecuten allí permanecen intactas.
- Antes de usar un modelo en la nube por primera vez, Solidon muestra claramente qué contenido sale del ordenador.
- El diálogo de programas adicionales muestra solo lo que aún falta y describe el estado de ComfyUI con palabras sencillas.
## 0.2.2


### Dibujo y modelado

- En el modo de boceto puede seleccionar y arrastrar puntos, líneas, círculos y contornos directamente en la vista. Una marca y un tirador indican además qué se moverá.
- El plano de dibujo permanece en el espacio al cambiar entre las vistas superior, frontal y lateral. Así ve su posición real en lugar de tres imágenes iguales.
- Puede terminar un rectángulo escribiendo su anchura y altura. Las medidas permanecen como restricciones en vez de perderse después de dibujarlo.
- En la vista frontal o lateral, tire de un contorno cerrado para darle altura. La cifra y la vista de alambre crecen con él; un valor escrito fija la altura exacta.
- Tire del contorno hacia fuera para crear un cuerpo o hacia dentro para crear un vaciado visible. Una flecha y una cruz permiten agarrar ambas direcciones.
- La vista previa muestra el prisma, cilindro o cuerpo de boceto mientras introduce sus medidas. Antes, los cuerpos nuevos no aparecían hasta aplicar el paso.
- Las herramientas de dibujo indican qué hará el siguiente clic. Las restricciones explican su efecto y selección, y los grados de libertad se describen con palabras claras.
- El cubo, el cilindro, el taladro y el vaciado aparecen una sola vez en el menú. La casilla «Editar caras y aristas más adelante» sustituye a la segunda entrada, antes llamada «exacto».
- Esa casilla mantiene disponibles chaflanes, redondeos, ángulos de desmoldeo, caras desplazadas y la exportación STEP. El diálogo nombra la ventaja, no el motor de cálculo.
- Al dibujar, la barra nombra el paso siguiente: Elevar, Rebajar o Terminado. Si falta un contorno cerrado o un cuerpo seleccionado, también lo indica.
- Una restricción se quita con un segundo clic en el mismo botón, y un clic derecho sobre el punto muestra qué depende de él. Antes cada clic añadía otra hasta que nada se movía.
- La barra de restricciones solo muestra lo que encaja con la selección actual. Si no hay nada seleccionado, allí hay una frase en lugar de diez términos técnicos en gris.
- Los cuerpos básicos se colocan «sobre la placa de impresión» en lugar de «en Z = 0», y la herramienta de dibujo se llama «curva», como lo que dibuja.

### Taladros y elementos

- Cambie directamente el diámetro de un taladro detectado en un modelo importado, sin volver a dibujarlo ni abrir un programa CAD.
- El taladro modificado conserva su posición y dirección y funciona en mallas y cuerpos exactos. Incluso un taladro inclinado permanece en su eje original.
- Las marcas de los elementos siguen la geometría visible después de recalcular. Un taladro marcado permanece abierto y la marca no tapa su abertura.
- Las herramientas frecuentes como Taladro, Unir y Restar están un clic más cerca en el menú. Los títulos siguen separando claramente los grupos.

### Bloques y piezas normalizadas

- El catálogo ofrece tornillos y tuercas imprimibles con roscas compatibles. Puede elegir cabeza, longitud, tamaño y holgura según la impresión.
- Los rodamientos habituales tienen un asiento con sus medidas normalizadas. Pueden quedar extraíbles con holgura o sujetos mediante ajuste a presión.
- Un taladro para tornillo puede alojar una cabeza avellanada o su arandela. La profundidad de cabeza decide cuánto se hunden en la pieza.
- Las tablas incluyen más arandelas, insertos roscados y rodamientos. Los tamaños técnicos se explican en la selección en vez de aparecer como códigos enigmáticos.
- Los alojamientos de imanes, clips y pasacables también aceptan medidas propias. Los campos adicionales solo aparecen si la variante elegida los utiliza.
- Los bloques están en el catálogo con imágenes de vista previa en lugar de como lista en el menú. Un clic derecho sobre la pieza elegida lleva allí.
- El catálogo avisa antes de insertar cuando falta el lugar en el cuerpo. La mayoría de los bloques necesitan una cara o un taladro seleccionado.

### Impresión y filamento

- Cada bobina puede tener sus propias temperaturas, refrigeración, retracción y valores de material. Se conservan al cambiar el nivel de calidad.
- Los valores de cada bobina llegan al archivo 3MF y al slicer en la posición de material correcta. Un color ya no toma por error los valores de impresión de otro.
- En el primer inicio, Solidon importa los filamentos cargados en el slicer con nombre, tipo, color y perfil del fabricante. No tiene que volver a crear las bobinas.
- Los ejemplos incluidos ya no sustituyen la impresora y el material elegidos por los ajustes usados para crear sus imágenes de vista previa.
- En el Flatpak de Linux, Solidon encuentra e inicia slicers del equipo, incluidos AppImages. Ambos programas pueden acceder a la carpeta de trabajo compartida.
- Al dividir se colocan pasadores en una mitad y los agujeros correspondientes en la otra. El mensaje indica cuántos son o avisa de que la cara de corte es demasiado pequeña.
- Tras dividir, las mitades se separan. Los pasadores y los agujeros ya no desaparecen entre dos caras de corte coincidentes.
- Al unir dos cuerpos, ambos conservan su descripción de filamento con su nombre. Antes podía perderse la descripción del segundo color.
- Al exportar a varias bandejas, los cambios de color se cuentan por bandeja. Una bandeja de un solo material ya no anuncia cambios que no ocurren al imprimir.

- Si el slicer configurado falla, el mensaje ofrece cambiar a otro. Antes solo quedaba exportar — incluso con dos slicers que funcionaban justo al lado.
- El archivo de impresión terminado se abre directamente en la ventana del slicer, con sus propios perfiles. Qué entrega usa usted se recuerda por proyecto.
- El archivo de impresión se comprueba contra la altura del modelo. Una pieza hundida bajo la placa se descubre antes de imprimir — no a media altura en la impresora.
- ElegooSlicer vuelve a aceptar trabajos. Y si un slicer coloca las piezas por su cuenta, el informe lo dice en vez de sustituir en silencio la ocupación planeada de la placa.
- El informe ya no apila mediciones viejas: una pasada nueva sustituye lo que vuelve a medir, el mismo hecho aparece una sola vez, y los avisos de volumen nombran el objeto en vez de un número.
- Los perfiles de slicer recordados saben a qué slicer pertenecen. Tras un cambio, ningún perfil ajeno pasa al programa nuevo.
- Un motivo de bloqueo bajo los ajustes de impresión desaparece en cuanto deja de valer. Antes, «necesita un perfil de impresora» seguía junto a un botón ya libre.

### Chat y generación 3D

- Los ajustes separan claramente los modelos en la nube y los locales. Antes de introducir una clave de nube explican qué datos salen del ordenador.
- Comprobar un generador 3D lento ya no deja sujeto el diálogo. Indica qué se está comprobando y cómo instalar los programas adicionales.
- La asignación de elementos detectados sigue siendo fluida en modelos grandes. Cientos de elementos se comparan juntos en lugar de uno tras otro.
- Las solicitudes a Ollama y ComfyUI en el mismo equipo evitan el proxy de la empresa. Un servicio local activo ya no aparece por error como inaccesible.
- En el Flatpak de Linux, la instalación y el inicio de programas auxiliares se ejecutan en el equipo, no en el aislamiento. ComfyUI también se encuentra en sus ubicaciones habituales.
- El botón Generar solo se puede pulsar cuando el clic de verdad inicia algo. Si falta algo, el diálogo dice qué — con un botón que lleva a la solución.
- Si la generación falla, la propia línea de error de ComfyUI aparece en el diálogo, junto con el paso en el que ocurrió. Esa línea es justo la que hace falta al pedir ayuda.
- Si un modelo de lenguaje escribe su llamada como texto en vez de ejecutarla, la propuesta lo explica — con el camino a «Comprobar las herramientas». Antes quedaba JSON en bruto en la conversación.
- El manual tiene una página nueva, «Qué modelos usa Solidon»: cuáles están probados, de dónde vienen y cuánto tardan. Para el camino desde texto dice qué archivo va en qué carpeta.
- Un cuerpo generado muy pequeño muestra su volumen real en vez de «0 mm³» junto a «cerrado».
- En los modelos de IA para generar, usted elige por tarea cuál calcula — como con el modelo de lenguaje. «Automático» sigue siendo la opción por defecto y toma lo que encaja.

### Vista y manejo

- La barra de parámetros mantiene las medidas compactas y visibles. Unidad, límites y expresión se cambian allí con deshacer, sin ocultar el propio valor.
- Los cursores de Solidon siguen el tamaño configurado del sistema en Windows, macOS y Linux. El punto de clic vuelve a estar en la punta dibujada y no a su lado.
- Pasar el puntero y seleccionar se marcan de forma claramente distinta. Los colores de análisis y diferencias siguen teniendo prioridad sobre el resaltado del cuerpo.
- Los menús, avisos y el manual usan palabras coherentes para principiantes. Los términos especializados se explican donde se necesitan por primera vez.
- El diálogo Apoyar explica antes de abrir PayPal que el pago es voluntario y no desbloquea funciones. Si falla el navegador, puede copiar el enlace.
- Vaciar y las demás herramientas dependientes muestran solo los campos usados por la variante elegida y explican de forma uniforme los valores ocultos.
- Los ejemplos incluidos se abren con una visita guiada. A la derecha se indica paso a paso qué hacer, y la visita reconoce por sí sola cuándo un paso está hecho.
- Las acciones propuestas para un error se conservan al guardar. Al reabrir un proyecto antes solo quedaba el error, sin la salida.
- La búsqueda de orientación examina cada posición una sola vez. Las posiciones propuestas varias veces costaban tiempo sin dar un resultado distinto.
- Los pasos del historial se pueden borrar y recuperar con Ctrl+Z. La pregunta previa nombra los pasos que dependen del borrado.
- Un doble clic en un paso agrupado del historial dice dónde están los pasos individuales. Antes no hacía nada, aunque las visitas guiadas enseñan justo ese gesto.
- Si un archivo se rechaza al leerlo, el indicador de carga desaparece. Antes se quedaba como si aún se calculara un archivo que no se había aceptado.
- Solidon arranca más rápido y el análisis de capas calcula con más soltura. Las bibliotecas de cálculo grandes solo se cargan cuando realmente hay que calcular.

- Los mensajes de error muestran los datos a los que sus frases se refieren. «El comienzo de la respuesta está al lado» — ahora de verdad lo está, junto con dirección y proveedor.
- Los consejos «Reducir triángulos» y «Abrir la página en el navegador» ahora son botones que hacen exactamente eso, en vez de frases que lo describen.
- Cuando un servicio no responde, el diálogo nombra la dirección para verla en el navegador y guarda el intento bajo «Detalles». Sus avisos solo señalan botones que existen.
- Las listas desplegables de las barras bajo la vista quedan abiertas hasta que usted elige. Antes, una lista podía cerrarse al instante porque se apartaba de debajo del puntero.
- El campo de grosor de la barra de corte espera a que termine de teclear. Antes cortaba con cada pulsación — primero con 3 mm y luego con 30.
- Tras abrir, el informe preselecciona el primer aviso que ofrece una acción. «Colocar sobre la placa» está ahí como botón de inmediato, sin tener que pulsar antes la fila.
- El aviso sobre piezas sueltas muy pequeñas ahora ofrece el botón «Eliminar las piezas pequeñas». Antes solo decía que no se había borrado nada y le dejaba buscar el camino a usted.
- Las reparaciones ya realizadas al importar aparecen como nota en el informe, no como advertencia. Antes el informe se abría en amarillo en uno de cada dos modelos, sin nada que hacer.
- El aviso sobre la gestión de paquetes cancelada nombra el botón por su nombre completo — en los seis idiomas. «Detalles» a secas era una pequeña búsqueda en cinco de ellos.

### Plataformas y correcciones

- Linux dispone ahora de un AppImage además del Flatpak. Así puede iniciar Solidon como un único archivo ejecutable sin instalar Flatpak.
- Una actualización de Windows iniciada desde Solidon solo muestra el progreso y vuelve a abrir Solidon después. Si inicia el instalador a mano, mantiene la opción de apertura en la página final.
- El Flatpak de Linux puede actualizarse desde Solidon.
- También se pueden enviar comentarios al soporte desde el paquete de Linux. Hasta ahora el paquete carecía del acceso de red necesario.
- En macOS, las grietas finas de la malla STL de una rosca se cosen al exportar sin aceptar una malla que haya empeorado.
- La comprobación de actualizaciones admite un changelog multilingüe amplio. Los avisos no terminan a media palabra y las listas largas ya no bloquean la comprobación.
- El diálogo Acerca de del paquete vuelve a mostrar los avisos de todas las bibliotecas incluidas.
- Los informes de errores muestran las versiones reales, la sesión y el método de entrada. Un guion ya no indica por error que falta una biblioteca necesaria.
- Los metadatos ajenos aislados ya no hacen que falle la reparación de una malla importada.
- Un vaciado correcto también indica en cuerpos exactos el grosor de pared y el volumen retirado, en vez de quedar en silencio después del cálculo.

## 0.2.1


### Colores y filamento

- Colorea caras y piezas con dos gestos en lugar de un pincel: un clic colorea una cara, un clic la pieza entera. Si un paso anterior cambia las medidas, el color se mueve con ellas.
- Un clic en la cara superior colorea la cara superior: el límite viene de la detección, sin radio y sin apuntar.
- El filamento se elige por nombre y color: «PETG rojo» en vez de un número. El chat también lo entiende.
- Veinte bobinas en la estantería son veinte filamentos en la selección. Cuatro bobinas del mismo material en cuatro colores son cuatro entradas, no una.
- El color de un filamento y sus temperaturas ahora van juntos. Antes, el ajuste del rojo podía acabar en el filamento blanco.
- El mismo color recibe la misma boquilla, también en la segunda bandeja.
- En el visor se ve el color real del filamento. Un filamento sin color propio es gris, y la selección sigue siendo reconocible.
- Colorear está ahora donde se busca el color; antes estaba bajo «Preparar».
- El campo «Color de la pieza» mostraba en el tema claro un color distinto al de la vista de al lado.
- Quien escribía «PETG» recibía «Este perfil de material no se conoce». Ahora el campo es una lista con los nombres que existen de verdad.
- La preselección «— ninguno —» se rechazaba al aceptar. Ahora hay allí un valor que el diálogo admite.
- El selector de color mostraba rojo, y tras deseleccionar la pieza quedaba gris.

### Bloques

- Una bisagra de pasador que sale de la impresora ya móvil. Nada que montar, nada que insertar: la impresora deja la holgura abierta.
- Un bloque puede reunir varias piezas. Así puede guardar un modelo móvil o ensamblado como una única entrada reutilizable del catálogo.
- Poner el pasador en el agujero no funcionaba, aunque ambos elementos estaban ahí. Ahora sí.

### Impresión y slicer

- Al cortar elige qué bandejas van. Quien quería cortar la bandeja 2 recibía tres archivos y las bobinas de la bandeja 1.
- Solidon escribe ahora también el perfil de máquina y de proceso para el slicer, en vez de remitir a su propio fondo. Siete ajustes había en el archivo, ciento treinta y seis llegaron al slicer.
- El código de arranque viene del perfil de impresora del fabricante en vez de escribirse a mano.
- Lo que ya no deposita un cordón lo dice la boquilla: las paredes demasiado finas figuran en el informe como hallazgo, no como propuesta.
- El límite inferior del grosor de pared viene del perfil de material. Allí había dos números fijos, y ambos eran falsos: en la Centauri son 0,84 mm.
- El botón de cortar invitaba a hacer clic aunque tres frases después no seguía nada.
- Un archivo de código G con la extensión .nc se podía abrir, pero no encontrar en el diálogo de apertura.

### Lo que Solidon ve en el modelo

- En archivos importados Solidon reconoce ahora agujeros y bolsillos también cuando la malla no está soldada. Antes no encontraba nada allí.
- El informe indica «varias piezas» solo cuando las hay. Una placa de una sola pieza contaba como 796.
- El mismo archivo ya no se examina quince veces. Eso ahorra los segundos que antes pasaban al abrir.
- Cuando la simplificación no llega hasta donde se pidió, Solidon lo dice. Hasta ahora quedaban 992 triángulos donde se querían 400, sin una palabra.
- El mismo aviso aparece una vez en el informe, no de nuevo tras cada paso.
- Dos cuerpos en el mismo sitio parecían uno, y nadie lo decía.
- Tras unir, un elemento apuntaba a otro agujero distinto del anterior.

### Chat y agente

- Mientras el agente trabaja, el chat muestra qué paso corre y con qué herramienta. Antes callaba hasta un minuto.
- La lista de modelos locales dice de cada uno con qué fiabilidad llama a las herramientas y cuánto tarda. Un modelo que solo escribe sobre ellas se reconoce ahora como tal.
- Si se corta la conexión con el modelo de lenguaje local, Solidon lo dice — y ofrece un camino en vez de anunciar un error de programa.
- Lo mismo vale si se corta la conexión con el servicio de imágenes.
- El chat nombra también los cambios pequeños de volumen. Un agujero hecho se anunciaba como «+0,00 cm³» y la propuesta parecía no haber hecho nada.

### Vista y manejo

- El árbol de objetos nombra pasadores y roscas, con diámetro y paso.
- Un paso que crea dos cuerpos figura con dos líneas en el árbol; antes había una.
- Si selecciona más cuerpos de los que toma una operación, ahora ve cuáles se usan.
- Imprimir mostraba el mismo tiempo distinto en dos sitios: «10 h 5 min» abajo, «605 min» en el diálogo.
- Números y unidades se leen igual en todas partes: una línea y su propia ayuda emergente nombraban el mismo volumen de forma distinta, y en pulgadas nada.
- Una medida admite una expresión en cada campo numérico; el manual muestra ahora también el botón.
- La rejilla del editor de bocetos mostraba la distancia del momento en que se entraba.
- Dos campos de texto se anunciaban como opcionales y nunca lo fueron.

### Corregido

- Duplicar daba al original un identificador nuevo, y el cuerpo desaparecía de la vista.
- Un cuerpo exacto del que un agujero no dejaba nada quedaba en el árbol como objeto vacío y podía guardarse.
- La vista de diferencias y los mapas de análisis callaban ante los cuerpos exactos.
- Un tipo de campo desconocido convertía en silencio cualquier campo en uno de texto.
- Un diálogo se dejaba aceptar, ponía un paso en el historial, y en la vista no cambiaba nada.
- Girar cero grados pasaba en silencio en vez de decir que no ocurre nada.
- La ventana de novedades mostraba setenta y cinco puntos como un muro. Ahora están agrupados, y el aviso llega en su idioma.

## 0.2.0


### Bloques
- Bloques propios sin una línea de código: seleccione pasos del historial y colóquelos en el catálogo como bloque — con campos propios, vista previa y un rango de valores a su medida.
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
