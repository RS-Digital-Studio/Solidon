# Novidades

Este ficheiro é o que aparece na janela de atualização, e nada mais. **Não** é
uma lista de alterações mas uma seleção, e escolher é o trabalho. Um ponto
pertence aqui se alguém der por ele ao usar o programa. Quantos sejam decide-o
a versão, não um número.

Portanto: nada de mensagens de commit, de nomes de módulos ou de números de
secção. «A barra desaparecia enquanto a aplicação ainda calculava durante
quatro segundos» é um bom commit e uma má entrada; «O progresso mantém-se até
o cálculo estar mesmo terminado» diz o mesmo a quem está à frente do ecrã.

Um ficheiro por idioma nesta pasta, tal como nos catálogos, e todos levam os
mesmos pontos pela mesma ordem (`tests/test_changelog.py`).
`tools/make_download.py` retira daqui a secção da versão atual e escreve-a em
`website/version.json`.

## 0.3.0


### Desenho e modelação

- No modo de esboço pode selecionar e arrastar pontos, linhas, círculos e contornos diretamente na vista. Uma marca e uma pega indicam também o que vai mover-se.
- O plano de desenho fica no espaço ao alternar entre as vistas de cima, frente e lado. Assim vê a posição real em vez da mesma imagem três vezes.
- Um retângulo pode ser concluído escrevendo a largura e a altura. As medidas ficam como restrições em vez de se perderem depois do desenho.
- Na vista de frente ou de lado, puxe um contorno fechado para lhe dar altura. A medida e a pré-visualização em arame crescem; um valor escrito fixa a altura exata.
- Puxe o contorno para fora para criar um corpo ou para dentro para criar uma bolsa visível. Uma seta e uma cruz tornam ambas as direções agarráveis.
- A pré-visualização mostra o bloco, cilindro ou corpo do esboço enquanto introduz as medidas. Antes, os corpos novos ficavam invisíveis até aplicar o passo.
- As ferramentas de desenho dizem o que fará o próximo clique. As restrições explicam o efeito e a seleção, e os graus de liberdade são descritos de forma clara.

### Furos e elementos

- Altere diretamente o diâmetro de um furo detetado num modelo importado, sem voltar a desenhá-lo nem abrir um programa CAD.
- O furo alterado mantém posição e direção e funciona em malhas e corpos exatos. Mesmo um furo inclinado continua no eixo original.
- As marcas dos elementos seguem a geometria visível após novo cálculo. Um furo marcado continua aberto e não fica tapado pela própria marca.
- As ferramentas frequentes como Furo, União e Subtração ficam um clique mais perto no menu. Os títulos continuam a separar claramente os grupos.

### Blocos e peças normalizadas

- O catálogo oferece parafusos e porcas imprimíveis com roscas correspondentes. Escolha cabeça, comprimento, tamanho e folga adequados à impressão.
- Os rolamentos comuns têm um alojamento com medidas normalizadas. O rolamento pode ficar removível com folga ou preso por ajuste à pressão.
- Um furo de parafuso pode alojar uma cabeça escareada ou a anilha correspondente. A profundidade da cabeça regula quanto entram na peça.
- As tabelas incluem mais anilhas, insertos roscados e rolamentos. Os tamanhos técnicos são explicados na escolha em vez de surgirem como códigos misteriosos.
- Bolsas de ímanes, clipes e passa-cabos também aceitam medidas próprias. Os campos adicionais só aparecem se a variante escolhida os utilizar.

### Impressão e filamento

- Cada bobina pode ter temperaturas, arrefecimento, retração e valores de material próprios. Esses valores mantêm-se quando muda o nível de qualidade.
- Os valores de cada bobina chegam ao ficheiro 3MF e ao slicer no lugar de material correto. Uma cor já não recebe por engano os valores de impressão de outra.
- Os exemplos incluídos já não substituem a impressora e o material escolhidos pelas definições usadas para criar as respetivas pré-visualizações.
- No Flatpak Linux, o Solidon encontra e inicia slicers do computador, incluindo AppImages. Ambos os programas conseguem aceder à pasta de trabalho partilhada.

### Chat e geração 3D

- As definições separam claramente modelos na cloud e locais. Antes de introduzir uma chave da cloud explicam que dados saem do computador.
- A verificação de um gerador 3D lento já não prende a janela. Mostra o que está a ser verificado e como instalar os programas adicionais.
- A atribuição dos elementos detetados continua fluida em modelos grandes. Centenas de elementos são comparados em conjunto em vez de um a um.
- Os pedidos ao Ollama e ao ComfyUI no mesmo computador evitam o proxy da empresa. Um serviço local ativo já não é indicado por engano como inacessível.
- No Flatpak Linux, a instalação e o início de programas auxiliares decorrem no computador, não na sandbox. O ComfyUI também é encontrado nos locais habituais.

### Vista e utilização

- A barra de parâmetros mantém as medidas compactas e visíveis. Unidade, limites e expressão podem ser alterados ali com anulação, sem esconder o próprio valor.
- Os cursores do Solidon seguem o tamanho configurado no sistema em Windows, macOS e Linux. O ponto de clique volta à ponta desenhada em vez de ficar ao lado.
- Passar o ponteiro e selecionar são marcados de forma claramente diferente. As cores de análise e diferenças continuam prioritárias sobre o realce do corpo inteiro.
- Menus, indicações e manual usam palavras coerentes para principiantes. Os termos especializados são explicados onde são necessários pela primeira vez.
- A janela Apoiar explica antes de abrir o PayPal que o pagamento é voluntário e não desbloqueia funções. Se o navegador falhar, o link pode ser copiado.
- Esvaziar e as outras ferramentas dependentes mostram apenas os campos usados pela variante escolhida e explicam de forma uniforme os valores ocultos.

### Plataformas e correções

- Para Linux há agora uma AppImage além do Flatpak. Assim, o Solidon pode iniciar como um único ficheiro executável sem instalar Flatpak.
- No Windows, uma atualização termina sem perguntas repetidas e volta a iniciar o Solidon. O Flatpak Linux pode ser atualizado a partir da aplicação.
- As mensagens ao suporte também podem ser enviadas a partir do pacote Linux. Antes faltava-lhe o acesso de rede necessário.
- No macOS, as fissuras finas da malha STL de uma rosca são cosidas ao exportar sem aceitar uma malha que tenha piorado.
- A procura de atualizações aceita um changelog multilingue extenso. As notas já não terminam a meio de uma palavra e as listas longas não bloqueiam a procura.
- A janela Acerca de do pacote volta a mostrar os avisos de todas as bibliotecas incluídas.
- Os relatórios de erro mostram versões reais, sessão e método de entrada. Um traço já não indica por engano que falta uma biblioteca necessária.
- Metadados estranhos isolados já não fazem falhar a reparação de uma malha importada.
- Um esvaziamento bem-sucedido também indica nos corpos exatos a espessura da parede e o volume removido, em vez de ficar silencioso após o cálculo.

## 0.2.1


### Cores e filamento

- Pinta faces e peças com dois gestos em vez de um pincel: um clique pinta uma face, um clique a peça inteira. Se um passo anterior mudar as medidas, a cor acompanha.
- Um clique na face de cima pinta a face de cima: o limite vem do reconhecimento, sem raio e sem apontar.
- O filamento escolhe-se por nome e cor — «PETG vermelho» em vez de um número. O chat também percebe.
- Vinte bobinas na estante são vinte filamentos na escolha. Quatro bobinas do mesmo material em quatro cores são quatro entradas, não uma.
- A cor de um filamento e as suas temperaturas passam a andar juntas. Antes, a definição do vermelho podia ir parar ao filamento branco.
- A mesma cor recebe o mesmo bico, também na segunda placa.
- Na vista aparece a cor verdadeira do filamento. Um filamento sem cor própria é cinzento, e a seleção continua a reconhecer-se.
- Pintar está agora onde se procura a cor; antes estava em «Preparar».
- O campo «Cor da peça» mostrava no tema claro uma cor diferente da vista ao lado.
- Quem escrevia «PETG» recebia «Este perfil de material não é conhecido». Agora o campo é uma lista com os nomes que existem mesmo.
- A pré-seleção «— nenhum —» era recusada ao confirmar. Agora há ali um valor que a caixa aceita.
- O seletor de cor mostrava vermelho, e depois de desmarcar a peça ficava cinzenta.

### Blocos

- Uma dobradiça de pino que sai da impressora já móvel. Nada para montar, nada para inserir: a impressora deixa a folga aberta.
- Um bloco pode ser feito de várias peças se disser antes de quantas. O teste de intervalo verifica-o também.
- Pôr o pino no furo não funcionava, embora ambos os elementos lá estivessem. Agora sim.

### Impressão e slicer

- Ao fatiar escolhe que placas seguem. Quem queria fatiar a placa 2 recebia três ficheiros e as bobinas da placa 1.
- O Solidon escreve agora também o perfil de máquina e de processo para o slicer, em vez de remeter para o seu acervo. Sete definições estavam no ficheiro, cento e trinta e seis chegaram ao slicer.
- O código de arranque vem do perfil de impressora do fabricante em vez de ser escrito à mão.
- O que já não deposita um cordão di-lo o bico: paredes demasiado finas ficam no relatório como constatação, não como proposta.
- O limite inferior da espessura de parede vem do perfil de material. Ali estavam dois números fixos, e ambos estavam errados: na Centauri são 0,84 mm.
- O botão de fatiar convidava ao clique embora três frases depois nada se seguisse.
- Um ficheiro de código G com a extensão .nc abria-se, mas não se encontrava na caixa de abertura.

### O que o Solidon vê no modelo

- Em ficheiros importados o Solidon reconhece agora furos e bolsas mesmo quando a malha não está soldada. Antes não encontrava nada aí.
- O relatório indica «várias peças» só quando as há. Uma placa de uma só peça contava como 796.
- O mesmo ficheiro já não é examinado quinze vezes. Isso poupa os segundos que antes passavam ao abrir.
- Quando a simplificação não chega ao pedido, o Solidon diz. Até agora ficavam 992 triângulos onde se queriam 400, sem uma palavra.
- O mesmo aviso aparece uma vez no relatório, não outra vez após cada passo.
- Dois corpos no mesmo sítio pareciam um, e ninguém o dizia.
- Depois de unir, um elemento apontava para outro furo diferente do anterior.

### Chat e agente

- Enquanto o agente trabalha, o chat mostra que passo corre e com que ferramenta. Antes ficava calado até um minuto.
- A lista de modelos locais diz de cada um com que fiabilidade chama ferramentas e quanto tempo demora. Um modelo que só escreve sobre elas passa a ser reconhecível.
- Se a ligação ao modelo de linguagem local cair, o Solidon di-lo — e aponta um caminho em vez de anunciar um erro de programa.
- O mesmo vale se cair a ligação ao serviço de imagens.
- O chat nomeia também as pequenas variações de volume. Um furo feito anunciava-se como «+0,00 cm³» e a proposta parecia não ter efeito.

### Vista e utilização

- A árvore de objetos nomeia pinos e roscas, com diâmetro e passo.
- Um passo que cria dois corpos aparece na árvore com duas linhas; antes havia uma.
- Se selecionar mais corpos do que uma operação leva, vê agora quais são usados.
- Imprimir mostrava o mesmo tempo de forma diferente em dois sítios: «10 h 5 min» em baixo, «605 min» na caixa.
- Números e unidades leem-se iguais em toda a parte: uma linha e a sua própria dica nomeavam o mesmo volume de forma diferente, e em polegadas nada.
- Uma medida aceita uma expressão em cada campo numérico; o manual mostra agora também o botão.
- A grelha do editor de esboços mostrava o passo do momento em que se entrava.
- Dois campos de texto anunciavam-se como opcionais e nunca o foram.

### Corrigido

- Duplicar dava ao original um novo identificador, e o corpo desaparecia da vista.
- Um corpo exato de que um furo não deixava nada ficava na árvore como objeto vazio e podia ser guardado.
- A vista de diferenças e os mapas de análise ficavam calados nos corpos exatos.
- Um tipo de campo desconhecido transformava em silêncio qualquer campo num de texto.
- Uma caixa deixava-se confirmar, punha um passo no histórico — e na imagem nada mudava.
- Rodar zero graus passava em silêncio em vez de dizer que nada acontece.
- A janela de novidades mostrava setenta e cinco pontos como um muro. Agora estão agrupados, e o aviso chega na sua língua.

## 0.2.0


### Blocos
- Blocos próprios sem uma linha de código: escolha passos no histórico e coloque-os no catálogo como bloco — com campos próprios, pré-visualização e intervalo de valores verificado.
- Um bloco construído por si viaja dentro do ficheiro de projeto. Quem o abrir pode inserir a sua peça sem ter de instalar nada.
- Cinco blocos novos no catálogo: gancho para painel perfurado, esquadro, pé, clipe de cabos e olhal de dobradiça.
- O gancho para painel agora aguenta mesmo que alguém levante a peça ao tirar algo — uma lingueta elástica encaixa atrás do painel. Desativável se tirar a peça muitas vezes.
- Suporte de parede, nervura, lingueta e ranhura, lingueta de encaixe, ligação de encaixe e dobradiça de filme aparecem já no menu de uma face clicada. Faltava justamente o suporte de parede.
- Quem insere um bloco do catálogo sem escolher um sítio é agora questionado. Até agora ficava na origem, metade dentro da peça e metade debaixo da placa.
- O catálogo de blocos pode ser visto mesmo sem modelo. Inserir fica então bloqueado e diz porquê, em vez de cancelar só depois da confirmação.
- O alojamento de porca e a folga para a cabeça do parafuso não tiravam nada: ambos construíam por cima da face em vez de por baixo.
- O alojamento do íman volta a segurar o íman: o lábio de retenção era até agora acrescentado ao alojamento em vez de escavado nele, e desaparecia lá dentro.
- A ranhura em buraco de fechadura fica agora suspensa na vertical, de modo que o parafuso encrava ao descer. Deitada de lado, deslocava-se para o lado e a cabeça não tinha espaço suficiente.
- O alojamento de porca encaixa agora na porca: para M5, M6 e M8 a tabela tinha uma altura demasiado pequena, seis décimas a menos no M5.

### Desenho
- Ao desenhar, a grelha mostra ao que o ajuste obedece, o passo pode ser escrito, as medidas ficam junto ao ponteiro e a barra diz em que face está a desenhar.
- Os atalhos de teclado voltam a funcionar no modo de desenho — linha, círculo, arco, aparar, deslocamento, Ctrl+Z — e o clique direito abre o menu do desenho em vez do modelo.
- Ajustar à vista traz de novo o desenho para o enquadramento, e um clique a cinco milímetros de um ponto já não se ajusta a ele.
- Uma linha auxiliar continua a ser uma linha auxiliar, mesmo depois de aparada, prolongada, deslocada ou espelhada. Até agora uma linha de centro tornava-se aresta de perfil e separava a peça.
- A janela de um passo mostra as medidas do seu desenho em vez dos valores predefinidos, e um círculo aparece com o seu diâmetro completo, não com metade.
- Uma cavidade feita a partir de um desenho com furo mantém o furo. Até agora fresava também a ilha.
- Um furo desenhado é subtraído seja qual for o sentido em que o desenhou. Conforme a ordem dos cliques saía antes uma peça mais cheia.
- Aparar corta agora apenas dentro do seu próprio troço, e Prolongar também encontra círculos e arcos como alvo — até agora só via linhas.
- Uma transição entre dois desenhos mantém os seus furos, e uma cavidade numa parede lateral corta na parede em vez de vir de cima.
- Um contorno que se cruza a si próprio é agora assinalado no desenho, em vez de gerar um corpo que não é estanque e ainda assim é exportado.
- Um desenho com furo dentro de furo mantém todos os níveis, e Projetar usa o plano em que está a desenhar — até agora o terceiro nível perdia-se e o corte vinha de baixo.
- Ao escalar para uma largura dada media-se também uma linha auxiliar. De cinquenta milímetros saíam cinco.

### Histórico e passos
- No histórico é possível selecionar vários passos de uma vez.
- Os limites de uma medida podem ser alterados depois — até agora valia para sempre o que foi introduzido ao criá-la.
- Alterar um passo depois já se pode desfazer. Até agora Ctrl+Z removia a ação errada e deixava ficar o valor alterado.
- Um passo que aponta para uma face de outro corpo recalcula após cada alteração. Até agora, uma peça alinhada ficava no sítio antigo, mesmo depois de fechar.
- As características mantêm o seu nome quando uma peça é rodada ou deslocada para imprimir. Os passos e ajustes que apontam para elas já não caem no vazio.
- Se a face até onde se extrude desaparecer, o erro aponta agora para esse campo e sugere escolher outra — em vez do plano do esboço.

### Ferramentas e geometria
- O escareamento só funcionava num sentido por eixo. Clicado do lado errado não tirava nada e não dizia nada.
- Em peças escalonadas, furo e tampão trabalhavam no ar: a direção vinha da caixa envolvente em vez do material naquele sítio.
- Um tampão passante enchia apenas metade do furo — e deixava à volta a folga com que o furo tinha sido alargado para o material.
- O enchimento em grelha punha barras ao lado da peça em vez de dentro da sua cavidade.
- O respiro de uma peça esvaziada termina agora na cavidade em vez de atravessar a tampa, e a ranhura roscada da tampa giratória já não abre um furo na sua própria parte de cima.
- Unir, subtrair e pintar avisam agora quando nada aconteceu. Até agora um passo ficava no histórico por cima de um modelo inalterado.
- Se uma peça se parte porque um bloco já não toca no seu suporte, o relatório assinala-o agora como erro e recomenda o que ajuda. Até agora o número de pedaços era apenas uma indicação.
- Uma rosca num furo clicado cortava só a metade de baixo. O mesmo acontecia com a bucha de inserção a quente.
- Uma rosca interior é agora subtraída, tal como o seu texto promete. Até agora crescia em vez disso um parafuso dentro do furo de núcleo.

### Impressão e slicer
- A estimativa de material para suportes estava errada por um fator grande: calculava a área sob a saliência em vez da coluna por baixo.
- A largura da ponte mede agora o troço realmente vencido sem apoio. Uma calha de cabos indicava antes a largura da sua caixa envolvente e recebia o conselho errado.
- Uma peça mais fina do que uma camada impressa já não é posta ao alto.
- A divisão automática conta a saliência do pino para o limite da mesa e não deixa ajustes a apontar para sítios que desapareceram.
- As montagens já respondem também a «Pousar na mesa»: descem como um todo, as peças mantêm a sua posição relativa. Até agora não acontecia nada, sem aviso.
- A quantidade de filamento lida de um ficheiro G-code volta a estar correta. Um comando no fim do ficheiro fazia calcular tudo o resto de forma diferente e duplicava o total.
- Uma mudança de impressora ou material mantém o que definiu. Até agora todo o conjunto era reposto sem aviso.
- A escolha de filamento por ranhura de material chega ao slicer. Era guardado o texto mostrado em vez do perfil.

### Vista e utilização
- Uma face selecionada conta: furo, bloco e esboço vão para onde apontou. Antes cada operação numa face custava dois cliques.
- Um clique num furo propõe agora o parafuso que realmente passa por ele — e indica o diâmetro medido.
- Depois de «Deslocar face» as faces da peça voltam a poder ser clicadas. Até agora não restava nada onde desenhar, furar ou definir um ajuste.
- Ao abrir um projeto aparece de imediato um indicador de carregamento. Até agora o centro da janela ficava preto durante segundos ou mostrava o ecrã inicial — parecia uma falha.
- Um clique na vista acerta agora apenas no que realmente vê — nenhuma peça oculta e nenhuma de outra placa. E depois de passar pelo modo Mover, as arestas deixam de aparecer através de todas as faces.
- As vistas de eixo de Ctrl+0 a Ctrl+6 voltam a enquadrar o modelo, em vez de incluírem também a placa e o volume de impressão.
- Quem deslocou muito uma peça e depois a roda, volta a rodar em torno da peça e não em torno de um ponto ao lado.
- Uma medida na vista usa agora a unidade que definiu, uma mudança de tema recolore também a placa e o volume de impressão, e com várias placas a etiqueta e a pega ficam na peça em vez de ao lado.
- O que um bloco inserido traz consigo fica na árvore de objetos sob o seu nome, e o nó propõe alterar precisamente esse passo.
- A sombra debaixo da peça mostra agora cada pedaço em separado e é mais discreta. Se um corpo se parte, agora vê-se na sombra.

### Ficheiros e exportação
- Dois ficheiros importados com o mesmo nome já não se perdem. O segundo sobrepunha-se antes ao primeiro, e o projeto deixava de poder ser aberto depois.
- Um endereço sem extensão de ficheiro diz agora que ali está uma página web e onde fica o botão de transferência, em vez de «Formato não reconhecido».
- Na exportação, peças com o mesmo nome sobrepunham-se: um ficheiro, duas mensagens de sucesso, uma peça perdida.
- A extensão de projeto é agora acrescentada por «Guardar como». Um projeto guardado como suporte.stl era, ao abrir, um modelo estranho ilegível.
- Um projeto alterado já não se perde quando arrasta um ficheiro para o ecrã inicial — é perguntado antes.

### Velocidade e estabilidade
- A aplicação já não desaparece sem aviso quando uma medida é alterada, um desenho é lido ou um corte é calculado. Os mesmos cálculos passam a ser até sessenta vezes mais rápidos.
- Esvaziar e colocar cavilhas podem mesmo ser cancelados. Numa peça digitalizada, o botão ficava parado durante minutos.
- Os ficheiros grandes de um slicer abrem sem que a janela congele. Antes, a mera contagem dos corpos lia o ficheiro todo para a memória.
- Se um cálculo em segundo plano encravar, a aplicação agora avisa. Caso contrário, a legenda, a análise de camadas e a procura de uma versão nova ficavam paradas para sempre.
- Cancelar descarta agora também a próxima execução já em fila, e a barra de progresso deixa de desaparecer sobre um ficheiro que ainda está a ser escrito.

### Idiomas
- O idioma escolhido no instalador aplica-se de imediato, senão o do sistema. E um idioma escolhido na janela tem efeito de imediato, em vez de só no arranque seguinte.
- Uma mudança de idioma passa a valer em toda a janela. As definições de impressão ficavam no idioma com que a aplicação arrancou.
- Os exemplos incluídos indicam agora as suas medidas no seu idioma. Antes lá estava «Breite, Tiefe, Höhe» em alemão, mesmo numa interface em inglês.
- A linha de comandos fala agora o idioma definido. Até agora dava ajuda e mensagens de erro em alemão, seja qual fosse a escolha.

### Chat e suporte
- Uma proposta do chat que retira passos diz antes quais vão com ela. E Cancelar cancela mesmo, em vez de continuar a calcular em segundo plano.
- O chat volta a conseguir oito passos por pergunta em vez de quatro, e a linha de custo já não calcula a mais.
- O que segue com uma resposta ao apoio é mostrado antes, ao pormenor — incluindo o registo. E se não chegar, a mensagem indica o motivo real.

### OpenSCAD
- As formas livres já não precisam de um segundo programa: o que o OpenSCAD fazia, fazem-no as ferramentas de desenho e os blocos — menos uma instalação de que tratar.
- Um projeto com código OpenSCAD continua a abrir e todo o resto é calculado como antes. O Relatório nomeia o passo e «Mostrar os valores» copia o seu código.

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
