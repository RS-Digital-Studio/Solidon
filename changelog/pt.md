# Novidades

Este ficheiro é o que aparece na janela de atualização, e nada mais. **Não** é
uma lista de alterações: de 97 commits entre a 0.1.1 e a 0.1.2 sobram oito
linhas, e escolhê-las é o trabalho. Um ponto pertence aqui se alguém der por
ele ao usar o programa.

Portanto: nada de mensagens de commit, de nomes de módulos ou de números de
secção. «A barra desaparecia enquanto a aplicação ainda calculava durante
quatro segundos» é um bom commit e uma má entrada; «O progresso mantém-se até
o cálculo estar mesmo terminado» diz o mesmo a quem está à frente do ecrã.

Um ficheiro por idioma nesta pasta, tal como nos catálogos, e todos levam os
mesmos pontos pela mesma ordem (`tests/test_changelog.py`).
`tools/make_download.py` retira daqui a secção da versão atual e escreve-a em
`website/version.json`.

## 0.2.0

- Blocos próprios sem uma linha de código: escolha passos no histórico e coloque-os no catálogo como bloco — com campos próprios, pré-visualização e intervalo de valores verificado.
- Um bloco construído por si viaja dentro do ficheiro de projeto. Quem o abrir pode inserir a sua peça sem ter de instalar nada.
- Seis blocos novos no catálogo: gancho para painel perfurado, suporte de parede, esquadro, pé, clipe de cabos e olhal de dobradiça.
- O gancho para painel agora aguenta mesmo que alguém levante a peça ao tirar algo — uma lingueta elástica encaixa atrás do painel. Desativável se tirar a peça muitas vezes.
- Uma face selecionada conta: furo, bloco e esboço vão para onde apontou. Antes cada operação numa face custava dois cliques.
- Ao desenhar, a grelha mostra ao que o ajuste obedece, o passo pode ser escrito, as medidas ficam junto ao ponteiro e a barra diz em que face está a desenhar.
- No histórico é possível selecionar vários passos de uma vez.
- Os limites de uma medida podem ser alterados depois — até agora valia para sempre o que foi introduzido ao criá-la.
- A estimativa de material para suportes estava errada por um fator grande: calculava a área sob a saliência em vez da coluna por baixo.
- O escareamento só funcionava num sentido por eixo. Clicado do lado errado não tirava nada e não dizia nada.
- Em peças escalonadas, furo e tampão trabalhavam no ar: a direção vinha da caixa envolvente em vez do material naquele sítio.
- Um tampão passante enchia apenas metade do furo — e deixava à volta a folga com que o furo tinha sido alargado para o material.
- O enchimento em grelha punha barras ao lado da peça em vez de dentro da sua cavidade.
- Uma rosca num furo clicado cortava só a metade de baixo. O mesmo acontecia com a bucha de inserção a quente.
- O alojamento de porca e a folga para a cabeça do parafuso não tiravam nada: ambos construíam por cima da face em vez de por baixo.
- Uma peça mais fina do que uma camada impressa já não é posta ao alto.
- A divisão automática conta a saliência do pino para o limite da mesa e não deixa ajustes a apontar para sítios que desapareceram.
- Uma cavidade feita a partir de um desenho com furo mantém o furo. Até agora fresava também a ilha.
- Um clique num furo propõe agora o parafuso que realmente passa por ele — e indica o diâmetro medido.
- Um ficheiro de um slicer chegava com corpos duplicados: uma peça com dezassete objetos era lida dezassete vezes, com o dobro do volume e do tempo de impressão.
- Ao escalar para uma largura dada media-se também uma linha auxiliar. De cinquenta milímetros saíam cinco.
- Na exportação, peças com o mesmo nome sobrepunham-se: um ficheiro, duas mensagens de sucesso, uma peça perdida.
- Uma mudança de idioma passa a valer em toda a janela. As definições de impressão ficavam no idioma com que a aplicação arrancou.
- Uma mudança de impressora ou material mantém o que definiu. Até agora todo o conjunto era reposto sem aviso.
- A escolha de filamento por ranhura de material chega ao slicer. Era guardado o texto mostrado em vez do perfil.
- Um projeto alterado já não se perde quando arrasta um ficheiro para o ecrã inicial — é perguntado antes.
- Uma proposta do chat que retira passos diz antes quais vão com ela. E Cancelar cancela mesmo, em vez de continuar a calcular em segundo plano.
- Um relógio mal acertado já não leva a demo consigo: um computador com a data no futuro queimava o prazo definitivamente.
- Quem tem licença já não é convidado a comprar quando um ficheiro do programa está danificado, mas fica a saber o que se passa mesmo.
- Um ficheiro de projeto de outra pessoa avisa antes do primeiro cálculo se traz código-fonte para um programa externo — por qualquer via e a qualquer profundidade.


## 0.1.5

- O desenho passa a acontecer na própria vista: a superfície de desenho coloca-se sobre o modelo em vez de o substituir, e um clique coloca um ponto no plano do esboço.
- A grelha da superfície de desenho mostra de novo aquilo a que se ajusta. Esteve algum tempo num décimo de milímetro e ficava meio escondida atrás da barra.
- Um clique no meio de um furo seleciona o furo. Antes acertava na face ao lado ou em nada, e na vista de cima chegava a anular a seleção.
- Um clique dentro de um recorte retangular seleciona a peça em vez de anular a seleção.
- O chat encontra agora o seu modelo local, escreva o endereço como escrever. Até aqui tinha de ser o endereço completo terminado em /api/chat.
- Uma chave de acesso recusada pelo fornecedor deixa de bloquear o seu modelo local. O chat passa sozinho para o modelo disponível seguinte em vez de enviar de novo a mesma chave.
- As mensagens de erro do chat dizem a que modelo se referem. Por cima de um erro de chave estava apenas que o modelo de linguagem não tinha respondido.
- O campo do endereço de um serviço dá um exemplo e avisa que ali não vai uma pasta. Se introduzir uma, ele volta com o motivo por cima.
- A janela de configuração deixa de fechar com erro quando um campo de endereço contém um caminho de pasta, ou o campo da chave um texto colado por engano.
- Os menus pendentes voltam a mostrar todas as entradas. Assim que um campo tinha o foco do teclado, faltava meia entrada no menu aberto.
- Ctrl+Z e Ctrl+Y aparecem agora na sua entrada de menu, tal como os outros catorze atalhos. Sempre funcionaram; apenas nada os nomeava.
- As mensagens de erro durante o desenho dizem que limite foi ultrapassado. Por cima de «entre três e sessenta e quatro vértices» estava apenas «A entrada não podia ser usada assim».
- As ações reunidas estão no mesmo menu e aparecem apenas uma vez na pesquisa de comandos, como esvaziar e esvaziar com exatidão.
- Uma entrada de menu «Rosca» diz agora para onde vai a rosca — para um furo ou para um perno.
- A interface espanhola nomeia as características da mesma forma em todo o lado. Na mesma lista havia antes duas palavras para a mesma coisa.
- A aplicação liberta memória ao fechar uma janela e termina de forma mais limpa.
- A imagem que segue com um comentário mostra agora também o modelo. Antes havia no centro uma superfície preta, precisamente onde está a peça em questão.


## 0.1.4

- Durante a demonstração, o Solidon pergunta uma vez: ao fim de meia hora de trabalho, um cartão pousa sobre a vista e pergunta como está a correr. Não para nada, e sem o seu clique não sai nada.
- Quem clica numa face e insere um elemento obtém-no perpendicular a essa face em vez de apontado para cima. Numa parede lateral, um furo para parafuso ficava antes atravessado.
- Um elemento colocado num furo assume a sua medida. Num furo de 5,19 mm, o casquilho de pressão propunha antes M3, que ali não remove nada.
- Um clique com a mão um pouco trémula volta a selecionar em vez de deslocar a peça um décimo de milímetro.
- Uma peça selecionada move-se diretamente com o rato — agarrar e arrastar, sem ir primeiro a «Mover». A pega fica para o preciso: por eixos e em passos de grelha.
- De baixo vê-se agora através da base de impressão. Quem trabalha a face inferior de uma peça roda a vista por baixo e vê a peça em vez da base.
- Um furo também pode ser selecionado clicando no meio dele, não apenas na sua parede.
- A pesquisa de comandos entende agora palavras do dia a dia: «copiar», «apagar», «abrir» e «colorir» não levavam a lado nenhum, embora as quatro existam.
- A pesquisa encontra também para quem não conhece o termo técnico. Ao escrever «reforçar», «encaixar» ou «aparafusar» chega-se à nervura, ao gancho e ao furo para parafuso.
- Duas entradas de menu chamavam-se ambas «remalhar». Agora são «Refinar arestas» e «Uniformizar triângulos»: a primeira divide arestas longas, a segunda iguala os tamanhos.
- O programa fala a língua que ouve noutros lados: «corpo exato» em vez de «B-Rep», cama em vez de superfície de impressão, placa para a disposição.
- Ao iniciar, o Solidon verifica se existe uma versão mais recente e oferece-a. Só é transferida e instalada com a sua confirmação; pode ser desativado nas definições.
- Um modelo de linguagem local pode agora calcular dez minutos. Antes, o chat desistia ao fim de dois e pedia um relatório de erro, por um cálculo que simplesmente demorava mais.
- Um anel é reconhecido como uma única característica e já não como três cordões sobrepostos.
- A entrada «Espessar superfície» faz agora o que promete. Antes deslocava a superfície.
- O título da janela indica o modelo aberto, mesmo quando ainda não existe um ficheiro de projeto.
- Ao desenhar, a medida fica na ponta da linha em vez de na margem da janela.
- Uma entrada de menu bloqueada diz agora porquê. O motivo já lá estava e era invisível.
- O relatório de erro leva o estado da cena: objetos com medidas, características, parâmetros e o histórico. Assim um erro reproduz-se em vez de se adivinhar.
- Foram corrigidas várias falhas ao fechar janelas e caixas de diálogo.

## 0.1.3

- O núcleo exato já sabe furar: «Fazer um furo exato» trabalha diretamente sobre o corpo exato, sem o desvio por uma malha.
- As concordâncias e os chanfros são reconhecidos com mais fiabilidade. Antes, uma concordância era por vezes indicada como um pino, com um diâmetro que não existia.
- Os exemplos incluídos já não recebem o utilizador com avisos que não o são.
- O ecrã inicial cabe em ecrãs pequenos, sem deslocamento.
- Uma característica selecionada colore-se a si própria. Antes, todo o corpo assumia a cor de seleção e não se via o que estava em causa.
- A árvore de objetos indica a medida de cada característica reconhecida.
- As malhas exportadas já não contêm triângulos vazios.
- Guardar duas vezes dá duas vezes o mesmo ficheiro.
- As cinco traduções foram revistas. Os termos técnicos passam a chamar-se como lhes chamam os slicers.
- A barra de ferramentas está arrumada: o campo mais largo era aquele de que menos se precisa.
- Um segundo erro do programa já não coloca uma segunda janela sobre a primeira.

## 0.1.2

- Os números decimais escritos são lidos corretamente em todo o lado. «12,5» continua a ser doze e meio; antes podia tornar-se 125, sem perguntar e sem avisar.
- Cada um dos cinquenta e seis campos das definições de impressão diz agora o que faz quando se mexe nele.
- O tempo de impressão e o material são estimados com mais rigor, sobretudo em peças ocas.
- A entrega ao slicer acerta na placa. Com o CuraEngine as peças ficavam ao lado.
- Ao dividir com pinos, os furos correspondentes ficam na metade certa.
- Milímetros e polegadas valem agora onde quer que apareça um número — também nas barras de ferramentas e ao pintar.
- O progresso mantém-se até o cálculo estar mesmo terminado, e a janela continua utilizável entretanto.
- Todos os atalhos de teclado estão agora numa única vista: no menu Ajuda, em «Atalhos de teclado», ou premindo a tecla de ponto de interrogação.
