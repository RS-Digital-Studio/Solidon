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

## 0.6.0

### Utilização e sistema

- No Mac, o Solidon precisa agora do macOS 14 ou mais recente. Qualquer Mac a partir de 2018 pode instalá-lo gratuitamente.
- O Solidon arranca agora nos Mac Intel com macOS 26. A versão 0.5.3 ficava aí bloqueada no arranque.
- No Mac, *Cancelar* interrompe de imediato uma resposta em curso do modelo local.
- No Mac, Return abre a entrada selecionada no ecrã inicial, em *Pesquisar função* e no relatório de verificação.
- No Linux, a escrita com Fcitx5 e IBus chega agora ao campo de texto também no Flatpak e no AppImage.
- A desinstalação no Windows não deixa no registo entradas da associação de ficheiros.
- Delete também funciona quando o separador *Seleção* tem o foco, e remove vários corpos marcados num só passo. Se a tecla não fizer nada, a barra de estado diz porquê.
- O clique direito nos corpos oferece *Remover objeto* e, com vários, *Unir*. *Esvaziar* está também numa face selecionada, que passa a ser a abertura.
- Os painéis da esquerda e da direita movem-se pela pega, encaixam num rebordo ou ficam a flutuar. *Vista → Painéis para o seu lugar* repõe-nos.
- Os painéis também podem ficar em baixo à esquerda, em baixo à direita e ao longo do rebordo inferior.
- Pode reordenar os separadores e arrastá-los para janelas próprias, também num segundo ecrã. Fechar a janela ou *Voltar ao Solidon* traz o conteúdo de volta.
- O Solidon guarda a disposição. As janelas continuam acessíveis mesmo quando um ecrã é desligado.
- Enquanto recalcula, o relatório de verificação diz *A recalcular …* e mostra as linhas anteriores como estado anterior. Até agora, os erros antigos pareciam continuar válidos.
- Se o cálculo rápido falhar num passo, o Solidon calcula-o a fundo na mesma execução em vez de parar.
- Uma constatação que diz que um passo não teve efeito abre esse passo no campo certo.
- Depois de remover um corpo, o relatório deixa de falar dele, e o histórico mostra que passos já não deixam nada.
- Um furo selecionado já não volta em silêncio ao seu corpo depois de recalcular. Até agora, o Delete podia então remover o corpo inteiro.
- Cada função tem o mesmo nome em todo o lado. A ferramenta *Dividir* oferece *Dividir por um plano*, *Dividir ao longo de uma linha desenhada* e *Dividir em peças soltas*.
- No corpo selecionado, *Dividir automaticamente …* está agora em *Preparar*.
- Na janela em repouso só *Blocos* se destaca a cor. O vermelho fica para os botões que descartam ou apagam, e as perguntas abrem com o foco em *Cancelar*.
- No modo de desenho, o separador *Seleção* fica oculto. A lista de restrições mostra as dos pontos e linhas selecionados, mais qualquer conflito.
- No cartão de parâmetros, uma medida só mostra «Não utilizado» quando é o caso. O botão diz quantos números fixos se podem associar a medidas.
- O relatório de erro só anexa um registo de falha quando o Solidon falhou mesmo.
- O cartão da visita guiada tem a altura dos seus passos. Um passo abre-se com um clique ou com a barra de espaços, e nenhum balão tapa mais a vista.
- Quando um passo da visita guiada aponta para o relatório de verificação, a visita continua visível. O separador fica emoldurado e o passo diz qual abrir.
- Um clique no i junto a uma ação do separador *Seleção* abre o manual onde essa ação é explicada.
- Cada cota de um bloco pode ser ligada com fx a uma cota do projeto, mesmo antes de ter uma expressão.
- Depois de arrastar a pega de uma pré-visualização, nenhum número fica sobre a vista. Um número escrito durante o arrasto move a pré-visualização, não o corpo escolhido.
- Depois de *Reparar e tentar de novo* e caminhos semelhantes, o histórico já não chama «eliminado» a um passo que continua a calcular. Se a cadeia voltar a parar, o passo fica marcado.
- O botão *Filamentos* está agora no cabeçalho. Lista os filamentos do projeto e leva ao inventário de filamentos.
- Outro filamento aparece de imediato, também em blocos e corpos STEP, e o Solidon não recalcula nada por isso. Os corpos selecionados mostram a cor do filamento sob o realce.
- No separador *Seleção*, o campo de filamento só atribui com um clique ou Enter. As setas e a escrita apenas percorrem a lista, e a roda do rato desloca o separador.
- Nas versões traduzidas, *Novo filamento* já não se desloca para o lado quando a janela é mais baixa do que o conteúdo.
- Os modelos grandes carregam visivelmente mais depressa e precisam de menos memória, também com um histórico longo e em computadores com 8 GB.
- Mesmo num histórico longo, um passo novo quase não demora mais a calcular do que o primeiro.
- Desfazer e refazer são mais rápidos, e a memória que já não é precisa fica logo livre.
- Resolver sobreposições e exportar em 3MF é bastante mais rápido.
- A área de trabalho aparece mais depressa ao abrir ficheiros 3MF grandes.
- Um modelo adicionado passa a ficar à vista, mesmo quando aparece ao lado de um modelo em que a vista estava ampliada.
- No catálogo de blocos, *Gerir blocos* aparece aberto enquanto ainda não existir nenhum bloco próprio.

### Imprimir e entregar ao slicer

- No Linux, o Solidon cria agora o ficheiro de impressão também com o Cura em Flatpak ou AppImage.
- No Linux, as impressoras do OrcaSlicer, Bambu Studio, ElegooSlicer e Creality Print em AppImage ficam disponíveis de imediato, mesmo que o slicer nunca tenha sido aberto.
- O diálogo de impressão oferece as impressoras do slicer escolhido, como *Primeiros passos* e *Definições*. Uma impressora assim adotada fica ligada ao seu slicer.
- No diálogo de impressão, o slicer muda-se como em *Primeiros passos*, também com *Escolher programa …* para um que o Solidon não encontra sozinho.
- Uma impressora da lista do Solidon e a mesma do slicer contam como um só aparelho. O diálogo escolhe o perfil com o bico certo e o ficheiro leva o código de início.
- Sem um perfil do slicer guardado, a exportação e a janela principal usam o que o diálogo de impressão propõe para a impressora, com a máquina e o processo do fabricante.
- Só são oferecidos os slicers com que o Solidon trabalha, além de slicers de resina como o ChituBox e o Lychee. O Bambu Studio em AppImage passa a contar também.
- O código de início e o volume de impressão vêm só da sua impressora, não de outro modelo da mesma série.
- O diálogo de impressão atribui os perfis do slicer muito mais depressa, ao abrir e após cada mudança de slicer.
- Com um slicer instalado, a exportação 3MF termina numa fração de segundo, pouco mais lenta do que a exportação STL.
- O tempo de impressão estimado está mais perto do do slicer, muito mais perto em peças com suportes.
- A verificação do espaço para suportes e skirt na mesa mede agora só sob as saliências. As peças junto ao rebordo já não recebem um aviso sem razão.
- As sugestões aceites quase já não deixam sem suporte as saliências que precisam dele. *Manter os canais livres* só bloqueia o espaço de onde um suporte já não se conseguiria retirar.
- Onde os suportes sob pequenas saliências assentam no modelo, o Solidon sugere suportes em árvore. Aí deixam menos marcas.
- Em pontas pequenas, o Solidon sugere uma *Velocidade mínima ao abrandar* mais baixa para que não amoleçam. A definição chega a qualquer slicer.
- Os rebordos estreitos que se sustentam sozinhos ficam livres com *Rebordos sem suporte*. Assim a impressão precisa de bem menos suporte.
- Os suportes saem com mais facilidade: a distância segue o material e a altura de camada de cada peça, também com vários materiais numa placa. A camada de separação segue a superfície acima.
- Se um suporte assenta na peça, o Solidon sugere também uma camada de separação por baixo, para que o seu pé não deixe marcas. Com suportes em árvore, só nos slicers que a imprimem aí.
- Com suportes em árvore e junto a uma torre de purga, o Solidon propõe a distância do suporte em camadas inteiras, tal como o slicer a imprime.
- Para PLA, o Solidon propõe mais espaço entre as muitas pontas finas e os suportes em árvore por baixo. Assim ficam menos resíduos das pontas dos suportes.
- Para PETG, o Solidon sugere arrefecimento total no suporte. Assim solta-se mais facilmente da peça.
- Novo nas definições de impressão: *Camadas de separação inferiores*, *Folga na camada de separação* e *Arrefecimento total no suporte*.
- O campo *Distância acima* chama-se agora *Distância acima e abaixo* e vale para os dois lados do suporte.
- Se o slicer recusar filamentos com temperaturas demasiado diferentes numa placa, o Solidon indica agora o motivo e o que fazer, em vez de dizer apenas que não foi criado nenhum ficheiro.
- No diálogo de impressão, impressora, filamentos e qualidade ficam totalmente visíveis também com letra ampliada. As legendas longas passam para a linha seguinte.
- O relatório de verificação calcula mais depressa e precisa de menos memória.
- No Linux com Flatpak, o Solidon indica agora que o slicer encerrou inesperadamente, em vez de dizer apenas que não foi criado nenhum ficheiro.

### Roscas, furos e peças normalizadas

- As roscas aceitam agora qualquer diâmetro até 1000 mm, com *Rosca imprimível*, num furo, com *Criar parafuso* ou *Criar tampa de rosca*.
- Os furos normais também podem ser criados e novamente tapados com diâmetros até 1000 mm. Os furos grandes e os escareados mantêm a forma redonda.
- Parafusos, porcas e anilhas existem segundo ISO de M1,6 a M64. Para outros tamanhos, *Medida própria* deriva as medidas dos tamanhos vizinhos e indica-o.
- Com *Ajustado ao furo*, *Pino para furo* constrói a contrapeça: uma cabeça escareada à face para um escareamento, uma rosca externa do mesmo tamanho e passo para uma interna.
- Numa rosca interna impressa, a seleção oferece diretamente *Pino para furo*.
- Se num furo estiver uma peça separada, como um pino, as ações no furo dizem-no e oferecem *Dividir em peças soltas*. Até agora, o pino fundia-se em silêncio com a placa.
- Novo: o *Perno roscado*, uma barra roscada ou um perno sem cabeça, chanfrado nas duas pontas, com a mesma rosca imprimível do parafuso e da porca.
- Também em furos de blocos como o furo de parafuso, a bucha de inserção a quente ou o alojamento de porca, *Pino para furo* cria o pino adequado, e avisa se o furo não está no corpo.
- Colocado à mão numa face, o alojamento de porca corta a sua bolsa no material. Até agora a bolsa ficava por cima e só o furo do parafuso era furado.
- O furo do parafuso do alojamento de porca atravessa exatamente a peça, mesmo uma espessa. Até agora terminava 10 mm abaixo da bolsa ou furava o lado oposto de uma fenda.
- Colocado por baixo, o alojamento de porca tem a bolsa sob a face e a ranhura desce até ela. Até agora a bolsa ficava meio por cima, com o parafuso na face.
- Se o furo de um bloco não atravessa a peça, chama-se agora cego. Até agora chamava-se passante.
- Se a parede for mais espessa do que o indicado em *Passa-cabos* ou *Espigão para mangueira*, o passo diz isso e abre a espessura de parede. Até agora a passagem acabava sem aviso no material.
- Se houver uma peça separada num escareamento, num furo oblongo, numa sede, numa garganta ou numa rosca, as ações dizem-no. Até agora era cortada ou fundida.

### Blocos

- Os blocos que são uma peça por si só, como clipes de cabo, nervuras ou porcas, surgem sem seleção como corpo próprio num sítio livre da placa, também num projeto vazio.
- Os seus próprios blocos também surgem assim como corpo próprio e não se prendem a um corpo que já está no projeto.
- Com *Guardar a seleção como bloco*, o corpo selecionado vem com exatamente os passos que o constroem. Se viesse um segundo corpo, o diálogo diz isso antes de guardar.
- Suportes de parede, abraçadeiras de tubo e de perfil e suportes aceitam qualquer parafuso de M3 a M64. Se um tamanho não combina com as outras medidas, o bloco diz o que mudar.

### Editar e esboçar

- Com *Mover característica*, o material da característica vai tal como está e o lugar antigo fica bem preenchido. Onde não for possível, a seleção di-lo logo.
- Em cordões e gargantas, a seleção só oferece o que a operação consegue fazer.
- Se houver um arredondamento junto a uma parede, *Aplicar o ângulo de saída* diz antes do cálculo que está a atrapalhar e indica *Remover característica* como saída.
- Ao cortar uma parte de um corpo, desaparecem também chanfros, roscas e alojamentos de porcas dos blocos que lá estavam.
- Em *Criar tampa* e *Criar tampa de rosca*, um campo vazio para a altura da abertura significa «Aresta superior», e 0 é a altura da mesa. Os projetos antigos mantêm a sua abertura.
- Uma restrição de ângulo num esboço pequeno já não vira as linhas.
- Um corpo levanta-se com três cliques: *Desenhar* na barra superior (Ctrl+Shift+E), depois canto, canto oposto, altura. Para fora une-se, para dentro recorta.
- Ao levantar, as medidas podem ser escritas. Um duplo clique no passo abre as suas medidas, e em *Tipo* passa a sólido de revolução ou padrão de furos sem desenhar de novo.
- No editor de esboços, *Concluído* leva de volta à vista e o clique seguinte põe a altura. Escape põe o contorno de lado, Ctrl+Z trá-lo de volta.
- Se um passo novo não puder ser calculado, o rascunho fica na vista e *Reparar e tentar de novo* calcula-o sem outro clique.
- Para modelar há quatro ferramentas, cada uma com o seu botão e atalho. A intensidade é um nível de 1 a 10, e passar de novo no mesmo sítio já não acumula material.
- O pincel ajusta-se ao tamanho do corpo. Se a malha for demasiado grosseira, *Modelar* uniformiza os triângulos no primeiro traço, e um Ctrl+Z desfaz ambos.
- Ao espelhar, o plano fica onde o corpo coincide consigo próprio, mesmo quando uma parte sobressai muito para o lado.
- Modelar acompanha o rato com fluidez, e até um passo com centenas de traços de pincel é calculado depressa.
- Em *Esqueleto*, cada clique depois do primeiro coloca um osso, Enter termina a cadeia, arrastar uma articulação dobra-a e *Concluído* guarda tudo sem diálogo.
- Um esqueleto só dobra o que está preso aos seus ossos, e o resto do corpo fica parado. Os projetos anteriores calculam-se como foram guardados.
- Com Ctrl ou Shift escolhe várias arestas e arredonda-as ou chanfra-as num só passo. Um clique num canto escolhe todas as arestas que lá se encontram.
- Num corpo exato, o realce de uma aresta mostra também as arestas tangentes contíguas que *Arredondar* e *Aplicar um chanfro* incluem.
- O que a seleção oferece numa característica, a operação executa com exatamente esses valores. O que está a cinzento, diz com a mesma frase, também por chat e linha de comandos.
- Como lugar da cópia, *Duplicar característica* propõe uma largura e meia ao lado do original, com uma parede entre ambas e nunca ao longo do seu eixo.
- Num escareamento, *Rodar característica* propõe o maior ângulo com que continua a sê-lo, e avisa quando uma rotação só repõe a característica sobre si própria.
- Se uma ação atingisse uma peça separada junto à característica, ou uma característica colocada tocasse outro material só numa linha, o Solidon diz isso em vez de danificar o corpo.

### Gerar com IA

- O diálogo de geração calcula localmente com TRELLIS.2 e FLUX.2 [klein] em vez de TripoSG e SDXL. Um texto passa primeiro a imagem, e a imagem a modelo.
- Antes de descarregar, a configuração indica as licenças e tamanhos dos modelos. Remove a antiga configuração TripoSG do Solidon e diz antes que pastas são e quanto ocupam.
- As paredes finas, por exemplo de um vaso, chegam fechadas e com espessura.
- O assistente responde na língua em que escreve.
- Com um modelo local, o assistente tem tanto espaço como com um alojado e cumpre tarefas até doze passos.
- Os modelos gerados chegam fechados com mais frequência. Onde as faces só se tocam, o Solidon separa-as e alisa pequenas dobras da superfície em vez de avisar de uma autointerseção.
- Se uma tentativa já se desfez ao gerar, a janela di-lo antes de a aceitar e oferece *Mais uma tentativa*.
- Se um modelo gerado for só uma pele fina à volta de um vazio, a janela di-lo antes de o aceitar e o relatório de verificação depois, com o caminho para uma nova tentativa.
- Antes de transferir, *Configurar o chat* e *Configurar o ComfyUI* indicam quanta memória gráfica e espaço um modelo precisa e se este computador os tem.
- Num Mac, *Configurar o chat* propõe um modelo local que cabe na memória partilhada e diz quando uma chave para um modelo alojado é melhor.

## 0.5.3

### Utilização e sistema

- À direita há um cartão com os separadores *Seleção*, *Relatório de verificação* e *Chat*. Os avisos novos já não trazem o relatório para a frente; o separador mostra-os com um símbolo e um número.
- No topo da janela encontra qualquer função em *Pesquisar função* (Ctrl+Shift+P). O mapa de funções segue a ordem da barra de menus.
- Na seleção, cada característica tem uma só ação aberta de cada vez. As outras ficam recolhidas e mostram os seus valores.
- Os diálogos de operação mostram à frente no máximo quatro campos e uma frase. Os valores raramente alterados estão em *Mais definições*, os limites em *Quando evitar?*.
- Um zero com significado diz no campo o que faz, por exemplo «automático», «sem» ou «do material».
- Todos os diálogos têm a mesma forma, com secções planas e uma margem comum para as etiquetas, também as definições, o diálogo de IA e a ativação.
- O relatório de verificação mostra primeiro as constatações e, por cima, uma linha com estado e contadores. *Exportar …* fica ao lado de *Entregar ao slicer …*.
- Constatações, passos da visita guiada e indicações são mais curtos. Onde um botão oferece a ação, a frase já não a repete.
- A ação *Reconstruir modelo* está no corpo selecionado.
- O ecrã inicial mostra em grande, no topo, as quatro formas de começar. *Primeiros passos* pergunta idioma, slicer e impressora e recolhe o resto.
- O catálogo de blocos mostra imagem e título em cada mosaico. Num furo, *Blocos adequados …* mostra só o que cabe num furo.
- O diálogo *Guardar a seleção como bloco* mostra uma linha por medida, com valor predefinido e limites.
- No Windows, o ponteiro do rato próprio do Solidon volta a clicar exatamente na ponta. Até agora o clique caía alguns píxeis ao lado.
- A pesquisa no manual já não termina com um erro quando mais um carácter deixa de encontrar resultados.
- Se anular ou eliminar um passo enquanto *Editar este passo* está aberto, o diálogo fecha-se e indica-o.
- Foi corrigido um bloqueio raro da aplicação durante a verificação de impressão.
- No Mac, as frases que indicam um atalho usam as teclas do Mac, ou seja ⌘, ⇧ e ⌥.
- No Mac, a tecla de apagar elimina corpos, características, passos do histórico e linhas de um desenho.
- No Linux, o atalho de refazer indicado na visita guiada e nas dicas também repõe um passo.

### Imprimir e entregar ao slicer

- Novidade: Anycubic Slicer Next com as 39 impressoras Anycubic, no Windows, macOS e Linux.
- No Linux, o Solidon encontra OrcaSlicer, Bambu Studio e PrusaSlicer instalados como Flatpak, com as suas impressoras e perfis, também a partir do Flatpak do próprio Solidon.
- No Linux, os slicers em AppImage também oferecem as impressoras de fabricante que neles configurou.
- No Mac, o Solidon passa a criar o ficheiro de impressão também com o Cura. Até agora só encontrava a janela do Cura.
- O Creality Print 7 traz as suas próprias impressoras e a última que escolheu.
- As listas de impressoras indicam cada impressora uma só vez, sem variantes de bico. O bico escolhe-se nas definições de impressão.
- Um bico escolhido nas definições de impressão mantém-se quando depois guarda as definições do programa.
- Se mudar o bico para o PrusaSlicer ou o SuperSlicer, o slicer recebe também o perfil de impressora correspondente.
- O Solidon oferece mais impressoras, também aquelas cujo perfil não indica mesa nem bico, como a Creality CR-20 e a Anycubic i3 Mega no PrusaSlicer.
- As definições de impressão mostram à frente slicer, impressora, bico, filamentos, qualidade, densidade de preenchimento e suportes; o resto está em *Mais definições*.
- Cada motivo de uma sugestão nas definições de impressão cabe numa linha. *Guardar o ficheiro de impressão* aparece assim que existe um ficheiro de impressão.
- As peças mais largas em cima do que na base já não recebem um aviso de margem quando o brim e o skirt ficam na mesa.
- Os suportes aceites chegam também por baixo das pontes com camadas finas. Até agora *Manter os canais livres* podia retirá-los aí por completo.
- Se os suportes estiverem ativados e não chegar nenhum ao slicer, o Solidon di-lo depois do fatiamento e indica a saída.
- O OrcaSlicer e o ElegooSlicer criam o ficheiro de impressão mesmo quando um perfil do fabricante contém valores que eles próprios rejeitam. O Solidon indica cada valor substituído.
- Quando um perfil indica uma ponta de suporte em árvore mais estreita do que a linha de suporte, o Solidon alarga-a para que o slicer calcule com suportes.
- Se um slicer aplicar uma definição de outra forma, o aviso indica o campo e os dois valores e leva às definições de impressão.
- No Linux, o Solidon oferece também o PrusaSlicer e o OrcaSlicer do gestor de pacotes com as respetivas impressoras do fabricante.
- Num Mac cujo sistema de ficheiros distingue maiúsculas e minúsculas, o Solidon encontra as impressoras do fabricante dentro do pacote do slicer.

### Furos, furos oblongos e divisão

- Uma rosca ou uma bucha de inserção a quente num furo selecionado já não para com «fora da superfície». Se o furo for demasiado largo, o Solidon indica tamanhos adequados.
- Num furo selecionado, a vista mostra só diâmetro, profundidade e duas cotas às arestas. As referências têm o nome do seu lado, por exemplo «Aresta exterior à esquerda».
- Em polegadas, a frase sobre um furo indica a sua medida em polegadas.
- A faixa de pré-visualização diz numa linha o que muda, com os comprimentos na sua unidade de apresentação.

### Modelar, texto e esboço

- Em suportes e placas com furos, escareamentos e texto, *Reconstruir modelo* cria agora um contorno com alojamentos subtraídos. Se não encontrar uma estrutura, di-lo.
- Se num esboço aproveitar o corte de um corpo convertido, os seus círculos e arcos chegam como círculos e arcos.
- Se uma peça não puder ser convertida em faces e arestas, o Solidon indica o motivo e uma saída em vez de terminar com um erro inesperado.

### Gerar com IA

- O aviso de IA diz em duas frases, por destino, o que é enviado. Como o texto mudou, confirma-o mais uma vez.
- As descrições dos modelos locais recomendados são mais curtas.

## 0.5.2

### Novas formas e blocos

- Nova é a forma base «Criar um tubo»: diâmetro exterior e altura, mais espessura de parede ou diâmetro interior, num só passo.
- Novo é o bloco «Patilha com furo»: uma patilha plana em qualquer face, com furo e medidas à medida do parafuso de M3 a M8.
- Nova é a «Abraçadeira de tubo» para tubos comuns de 15 a 40 mm ou qualquer medida própria até 110 mm, com parafuso de aperto M3 a M6 e a folga do seu material.
- Novo assistente «Recipiente com tampa»: redondo ou retangular, tampa de rosca, de encaixe ou articulada e, se quiser, compartimentos, inserto e furos de polvilhar. As cotas principais são parâmetros.
- Quatro suportes nascem num passo com faces e arestas verdadeiras: em U, redondo, em forquilha e com prateleira, fixados com buraco de fechadura, furos para parafusos, gancho de painel ou grampo.
- Novos são «Fecho de baioneta» e «Disco giratório com retenção», cada um como par a condizer, e «Manga de encaixe e conector de varetas» para duas a quatro varetas.
- Novos também «Espigão para mangueira», cuja passagem atravessa a parede, «Junta de calha» para calhas, e «Piso da divisão», «Parede da divisão» e «Vidro da janela» para divisões encaixadas.
- Uma cena vazia mostra como começar: paralelepípedo, cilindro, desenho, blocos ou um ficheiro que arraste para dentro.
- Os corpos novos aparecem na mesa em vez de num corpo selecionado, e ficam selecionados. Numa face escolhida assentam no ponto clicado ou ao centro e, se quiser, unem-se à peça no mesmo passo.
- Blocos como um alojamento de íman ou um furo para parafuso ficam onde clica na face. A sua distância a duas arestas mantém-se se a peça mudar depois.
- A «Lingueta para perfil de alumínio» serve no Motedis 20 × 20 tipo B ranhura 6 e 30 × 30 tipo B ranhura 8, com a cabeça à forma da ranhura. Os três tamanhos anteriores ficam como medidas antigas.
- No relatório, «Reconstruir modelo» refaz uma peça importada, também esquadros, gargantas e escareamentos, compara-a com o original dentro do limite escolhido e aplica-a num só passo.
- A «Abraçadeira com insertos» começa com o material do projeto nos dois campos de material. Até agora ambos ficavam vazios.
- A pesquisa de peças encontra a «Lingueta para perfil de alumínio» também como porca em T, e a sua descrição diz em que se distingue de uma porca em T com rosca.
- Uma tampa de «Criar tampa» pode ter dobradiça, impressa no lugar ou com um pino de «Pino para furo», e o colar é cortado para abrir livremente.
- Com «Rebaixar contraforma», um inserto recebe alojamentos para ferramentas que voltam a sair a direito.

### Imprimir e entregar ao slicer

- A preparação da exportação 3MF pode ser cancelada. Em trabalhos com várias placas, o Solidon reutiliza as camadas e sugestões já calculadas.
- Os filamentos não utilizados de projetos antigos deixam de ser enviados ao slicer. Os perfis continuam associados aos filamentos em uso.
- Os modelos adicionados encontram espaço também após a décima segunda placa. As placas importadas mantêm a sua disposição.
- Os modelos adicionados com filamentos diferentes ficam em placas separadas quando a impressora não tem bicos suficientes.
- Ao mudar de impressora ou de slicer, a mesa de impressão escolhida anteriormente deixa de ser transferida para o novo perfil.
- As peças esguias ficam mais perto do centro ao serem dispostas. O espaço da aba é ajustável; para bases pequenas é sugerida uma aba em contacto com a peça.
- Os perfis danificados no PrusaSlicer e no SuperSlicer são assinalados. O Solidon utiliza então o seu conjunto completo de definições de impressão.
- As definições de cada peça chegam ao slicer com mais fiabilidade. As que se aplicam a toda a placa são explicadas na peça afetada.
- Se aceitar um brim só para uma peça esguia, as restantes peças mantêm a sua própria escolha de aderência, e o campo indica as peças a que o brim se aplica.
- Com Orca e Prusa, aceitar uma sugestão de velocidade para um encaixe abranda apenas as peças afetadas.
- Mesmo pequenas alterações aceites nas definições de impressão são preservadas na exportação.
- O Cura usa os limites de jerk do perfil, com valores separados para paredes, enchimento e primeira camada.
- Se estiver selecionada outra impressora no Cura, a entrega identifica ambas e indica onde adotar a escolha do Cura.
- Corrigida uma falha do ElegooSlicer e do OrcaSlicer ao preparar modelos multicoloridos com suportes em grelha.
- Após fatiar, Solidon também compara o material de suporte e as camadas do modelo por placa. O relatório mostra a estimativa interna e os valores do ficheiro de impressão.
- A comparação de material considera apenas o modelo impresso. A purga aparece separadamente, com indicação quando a quantidade não pode ser lida por completo.
- A comparação do tempo de impressão conta a partir da primeira camada com as velocidades da sua impressora, também com suportes, e já não aponta um grande desvio em quase todas as impressões.
- A análise de camadas é várias vezes mais rápida em modelos ocos e em modelos com muitos tetos, e preserva os contornos finos. A vista de camadas aproveita o que o relatório já calculou.
- Nas peças sobrepostas, a análise de impressão deixa de contar o ar fechado como material. Também melhora a deteção de saliências e dos suportes necessários.
- No primeiro arranque e nas definições escolhe primeiro o slicer e depois uma das suas impressoras. A lista tem um campo de pesquisa, e volume e bico vêm do perfil do slicer.
- Se no primeiro arranque clicar em «Guardar e iniciar» enquanto o Solidon ainda procura as impressoras do slicer, a aplicação já não bloqueia.
- O bico escolhe-se nas definições de impressão entre os tamanhos que a sua impressora conhece, e o slicer recebe o perfil correspondente.
- As definições de impressão perguntam pela ordem em que uma coisa depende da outra: slicer, impressora, bico, placa, filamentos e qualidade, e depois os valores.
- Agora pode gerar ficheiros de impressão diretamente a partir do Solidon com o Creality Print 7.2 e 7.3.
- Com o Cura, o Solidon adota a pedido a impressora que o Cura está a usar, com o seu próprio bico. Uma impressora renomeada no Cura volta a ser reconhecida.
- O Cura fatia agora com o bico que escolheu, também nas impressoras da sua própria lista, e as impressoras com a origem no centro da mesa mantêm-na.
- As impressoras com a origem fora do canto da mesa, como delta, BIBO ou Dremel, recebem as peças onde o Solidon as põe. Antes ficavam na borda ou o slicer reorganizava-as.
- O Bambu Studio recebe a variante do bico e as temperaturas das suas bobinas, até ao ficheiro 3MF.
- Se escolher brim, skirt, raft ou «Automático» nas definições de impressão, só aparecem as medidas que o seu slicer recebe, sem campos que não teriam efeito.
- Um número fora do seu limite fica no campo, o limite aparece ao lado e «Fatiar» espera até estar certo. Até agora era cortado sem aviso.
- Peças altas e finas sobre uma base pequena recebem paredes mais calmas, a 60 mm/s e com menos aceleração. Na Centauri Carbon 2 essas hastes soltavam-se.
- Com o Cura, o relatório de verificação indica as peças que só recebem esses valores por arrasto, porque o Cura só os aceita para toda a placa.
- O Solidon só sugere «Parede exterior primeiro» para a peça que precisa dela, e nunca para uma com suportes.
- A pesquisa rápida de «Orientar para impressão» também verifica se uma peça fica de pé com segurança. Se uma não fica de pé em nenhuma posição, orienta mesmo assim as restantes e indica-a no relatório.
- Com «Dispor na mesa», cada peça vai para a primeira placa onde tem espaço. O conjunto de minigolfe precisa assim de quatro placas em vez de seis.
- Se arrastar um corpo na vista para outra mesa, ele fica na placa dessa mesa.
- Quando chega outro modelo, de um ficheiro, de uma transferência ou gerado, a vista mostra a placa em que está.
- Outro modelo vai para o espaço livre mais próximo do centro da placa, em vez do canto traseiro esquerdo.
- Depois do primeiro «Abrir no slicer …», o Solidon já não volta a calcular o histórico.
- A verificação cruzada com o SuperSlicer já não indica um código de arranque ignorado onde nenhum foi ignorado.
- O SuperSlicer já não falha com peças redondas: já não recebe a costura chanfrada que não conhece.
- O SuperSlicer recebe suportes em grelha com um aviso se foram escolhidos suportes em árvore. A costura mais próxima é aplicada sem avisos falsos.
- O TPU encontra o perfil de filamento e os valores de arranque no PrusaSlicer e no SuperSlicer. Se faltar um perfil, o Solidon indica que usa a sua própria tabela de materiais.
- O Cura respeita os limites de aceleração e indica os valores escolhidos reduzidos. O preenchimento sólido usa a sua velocidade; só a face superior usa a velocidade de superfície.
- O Cura usa a velocidade mínima do ventilador e o limiar de tempo de camada do perfil da sua impressora. Até agora o ventilador ligava já na primeira camada, onde devia ficar parado.
- A temperatura da câmara chega ao campo correto do slicer. Os perfis sem aquecimento regulável da câmara explicam por que o valor não tem efeito.
- O preenchimento Linhas chega ao Bambu Studio e ao Creality Print como linhas, sem ser substituído por Grelha ou Cúbico.
- Após o corte, o Solidon assinala definições descartadas pelo PrusaSlicer ou pelos slicers Orca, além de alterações à borda, ordem das paredes e tipo de suporte.
- A pré-seleção de filamento escolhe Generic ou a marca da sua impressora em vez de um filamento especial de terceiros, por exemplo Generic PETG em vez de BETA PETG na Bambu A1.
- Agora «Orientar para impressão», «Rodar» e «Deslocar» funcionam também em modelos de superfícies STEP, com rotações de quase 180° e em faces reconhecidas em parte. O corpo continua exato.
- Uma parede exterior mais lenta aplica-se agora também a perímetros pequenos como furos e hastes no PrusaSlicer e na família Orca.
- O PrusaSlicer e a família Orca respeitam a densidade de suporte escolhida. O campo começa em 1 %. Para imprimir sem suportes, escolha «Nenhum».
- Nas impressões multicoloridas com OrcaSlicer, ElegooSlicer, Bambu Studio e Creality Print, a torre de purga recebe uma posição inicial adequada ao tamanho da mesa.
- As peças demasiado grandes são indicadas antes de iniciar o slicer. Se não for encontrado espaço para todas numa placa, pode distribuí-las por várias placas.
- Os caracteres especiais nos nomes de projeto ou utilizador já não impedem criar o ficheiro de impressão. O Cura também lê modelos com nomes turcos ou chineses.
- O Solidon organiza na base as peças sobrepostas antes de fatiar com PrusaSlicer ou Cura e avisa se não encontrar uma disposição adequada.
- Se o PrusaSlicer ou o SuperSlicer indicar uma primeira camada vazia, o Solidon identifica a peça e permite colocá-la na placa ou abrir as definições de impressão adequadas.
- Os avisos do PrusaSlicer e do SuperSlicer aparecem no relatório mesmo quando o slicer conclui, e uma camada vazia como erro. A distância ao raft ajusta-se à parte.
- Se o slicer dividir uma placa em vários ficheiros de impressão, o Solidon indica-o e propõe dispor ou exportar. Antes ficava em silêncio só com um deles.
- No topo do relatório vê se a transferência está pronta, precisa de uma decisão ou não é recomendada, e o que falta verificar. Sem constatações, uma peça já não conta por si só como pronta a imprimir.
- Uma constatação selecionada indica a sua consequência para a impressão, e cada ação proposta diz o que muda além disso.
- Após exportar ou «Abrir no slicer …», o Solidon volta a ler o ficheiro. O registo no relatório indica ficheiros, destino de impressão, material, definições e se o ficheiro corresponde ao pedido.
- Exportado como 3MF na linha de comandos, um corpo de uma só cor mantém o seu filamento ao ser reaberto.
- Para definições de peças individuais, a linha de comandos indica que peças são e que valor recebem.
- Se aceitar suportes para uma ponte longa sobre a própria peça, eles chegam agora também aí. Antes juntava-se «Só da mesa», e vários slicers imprimiam a ponte sem suporte.
- As peças pequenas deitadas, como parafusos, já não recebem suportes propostos onde uma aresta de corte mostrava por engano um ponto a flutuar.
- Se uma peça acaba no topo numa aresta que o slicer não imprime, o Solidon já não avisa de um modelo cortado depois do fatiamento.
- Se a primeira camada de uma peça for mais estreita que uma linha, a mensagem depois do fatiamento propõe as linhas de parede e o raft como saída.
- O SuperSlicer mantém a disposição do Solidon e já não empurra as peças até à borda da mesa; a saia fica na mesa.
- Se uma peça só cabe na mesa rodada, segue rodada para OrcaSlicer, Bambu Studio e ElegooSlicer; se ao Creality Print não chegar a margem, o Solidon avisa antes.
- O Solidon só propõe uma aba tão larga quanto a mesa permite.
- Se a borda em volta de uma peça entra numa zona de exclusão da mesa, a verificação antes da exportação avisa.
- Se no slicer se cruzam os percursos de duas peças, ou de uma peça e da torre de purga, a mensagem diz isso e propõe saídas.
- Se a aba estiver em automático, o Solidon avisa antes de exportar quando ela pode passar da mesa ou entrar numa zona de exclusão, e propõe uma largura fixa.
- Os suportes e a saia junto à borda da mesa contam na verificação antes da exportação, com o alargamento da primeira camada de suporte que o perfil do slicer indica.
- Os ficheiros STL exportados a partir de peças STEP não contêm triângulos sem área.

### Furos, furos oblongos e divisão

- O ângulo de um furo oblongo num furo importado aponta na direção esperada e mantém-se ao mudar a finura.
- Um furo oblongo numa parede lateral virada para a esquerda ou para a direita pode ser encurtado, estreitado e rodado. Projetos de versões anteriores mantêm os furos oblongos até alterar o passo.
- Em corpos STEP, um furo oblongo numa face inclinada já não conta como saliente de lado, e um segundo arrasto num furo oblongo que entra num degrau já não enche o corpo.
- Um furo oblongo através de uma chapa inclinada ou chanfrada mostra toda a profundidade em corpos STEP, e a sua cópia para lá da borda dá a mesma mensagem em peças STL e STEP.
- Num corpo com faces e arestas verdadeiras, um bloco colocado depois de um furo fica na face escolhida, e «Criar tampa de rosca» também funciona na borda de uma caixa esvaziada.
- Duas placas que se tocam continuam um só corpo num furo e mantêm o material, quer o estique, altere, desloque ou feche. Um pino por cima fica no lugar.
- Esticar um furo que atravessa dois corpos já não indica que o corpo se parte quando isso não acontece.
- Se um furo corta o corpo em dois, o relatório di-lo uma só vez, com o número de peças no fim, e cala-se assim que o corpo volta a ser uma peça.
- Os padrões em faces cilíndricas de modelos importados ficam fechados ao alterá-los.
- No histórico de um corpo STEP pode reordenar passos ou inserir um antes, mesmo que um passo posterior se refira a um furo. A referência segue o furo.
- Um furo simples ou um furo oblongo deslocado ou duplicado com uma nova direção continua exato num corpo STEP.
- Uma característica reconhecida a mais de um metro da origem mantém o seu lugar ao alterá-la. Antes o campo cortava o número sem aviso, e o furo mudava de sítio.
- Se um passo atinge uma peça cuja superfície se cruza a si própria, para e mostra o sítio. Fora dela continua a calcular e avisa que as peças não puderam ser unidas.
- Agora «Dividir o modelo» corta uma figura também ao longo da sua costura de simetria sem a deixar aberta, e os pinos já estão no lugar na pré-visualização.
- Se um corte só roça uma parede, «Dividir o modelo» indica o sítio e leva à posição do corte em vez de falhar nos pinos.
- Cortar fora corta agora também em ângulo: em cima escolhe o «Plano» — num eixo com inclinação, paralelo a uma face, por uma aresta ou por três pontos que clica na vista.
- Um corpo STEP continua um corpo STEP ao cortá-lo, com as suas faces, arestas e nomes.
- Uma tampa de rosca acabada de criar já não aparece no relatório como demasiado justa para o gargalo.
- Se um furo não puder ser cortado de forma limpa num corpo STEP, o Solidon fura-o no modelo de triângulos em vez de passar adiante um corpo danificado.
- Se escolheu «Carregar agora», também as peças de «Dividir o modelo» deixam de iniciar minutos de reconhecimento; «Reconhecer todas as características» recupera-o.
- Ao escolher «Dividir o modelo» numa linha de resumo do relatório para vários corpos, o Solidon divide-os um a seguir ao outro. Antes só dividia o primeiro.
- Se ao «Unir» um corpo tapa um furo total ou parcialmente, o relatório indica-o com o local e a cavidade que resta.
- Os padrões circulares e «Espelhar» tomam o seu «Centro de rotação» de um corpo, uma característica, um ponto ou a origem. O centro fica fixo mesmo que o corpo se mova depois.
- Um arrasto dentro da abertura de um furo escareado selecionado deixa o corpo onde está, e a linha de estado indica o caminho para o furo oblongo. Até agora movia o corpo inteiro.
- Quando o cartão de cotas de um furo fica alto, as outras cotas ficam junto ao corpo, e a pega para deslocar fica na boca em vez de dentro da peça.
- Se selecionar um furo feito no Solidon, o seu diâmetro aparece só no cartão de cotas na vista. Até agora aparecia uma segunda vez à direita.
- Uma direção que introduz à direita para um furo oblongo passa também para o cartão de cotas na vista, e «Aplicar» continua disponível. Até agora voltava ali a 0°.
- O Solidon reconhece cones, também planos e curtos, arredondamentos e faces estreitas da mesma forma em mais modelos, quer o modelo esteja deslocado, rodado ou escalado.
- Um topo abaulado chama-se também em corpos STEP «Face curva» em vez de «Arredondamento», e peças STL arredondadas em toda a volta mostram cada arredondamento, como a mesma peça em STEP.
- Letras e contornos curvos de modelos importados já não mostram arredondamentos falsos.
- O Solidon reconhece cada campo de nervuras, favo de mel ou saliências de um ficheiro importado como um só padrão, e «Reconhecer características neste local» junta as células de um campo.
- Um campo pequeno que o Solidon só lê como características soltas passa a ser um padrão com «Agrupar como padrão». Os padrões em ficheiros STEP são reconhecidos diretamente.
- As peças de uma divisão automática também são numeradas em projetos de versões anteriores, e um corte apagado ou desativado deixa de contar.
- Um furo que duplica, desloca ou repete ao longo de uma face inclinada continua a ser o mesmo furo em peças STL e STEP, com as mesmas medidas e mensagens.
- Após «Repetir característica», uma cópia numa peça STEP já não fura até ao topo, e um furo STL de facetas grosseiras continua a contar como passante.
- Uma rosca aumenta ou diminui com «Alterar característica» sem romper a parede, e a rosca oposta de um ajuste roscado muda com ela.
- Um par de roscas impressas passa a verificação de ajuste: as duas roscas indicam a medida com que são construídas, e a verificação espera a folga das duas metades.
- Com «Verificar o percurso de montagem», as peças também podem rodar, ou ser inseridas e depois rodadas como uma baioneta.
- Uma peça de «Criar peça de ensaio» recorta a mesma janela das duas partes de um ajuste e indica a folga.
- Um furo escareado que, depois de duplicar, deslocar ou repetir, termina todo dentro do material já não avisa que sai pela aresta.
- Se o escareado de uma cópia passa de um lado, o Solidon volta a encontrar a cópia da mesma forma em peças STL e STEP.
- Se duplicar um furo ao longo do seu próprio eixo para o vazio, o original mantém o nome em peças STL, e a cópia é dada como perdida como em peças STEP.
- Uma garganta ou um cordão que uma abertura divide em dois arcos aparece nas peças STEP como um único anel na árvore, como nas peças STL e 3MF.
- Características iguais em peças STEP, como dois troços de uma superfície cónica, mantêm o nome quando fura, duplica, altera um furo ou insere uma peça noutro sítio.
- As características que pertencem juntas aparecem como grupo na árvore de objetos, e câmaras e fechos mudam como um todo: medida interior, profundidade, folga e curso de rotação.

### Arredondar e chanfrar

- Arredondar um grupo de arestas num corpo STEP arredonda agora as arestas possíveis em vez de recusar tudo. «Mostrar o ponto» encontra cada aresta omitida.
- As arestas junto a uma parede não mais espessa do que o raio ficam vivas, e o relatório indica o raio que cabe ali. Antes, todo o arredondamento era recusado.
- Se um corpo STEP não tiver aresta própria num local escolhido, o relatório oferece «Terminar a edição de faces e tentar de novo». No modelo de triângulos também é arredondado.
- Se faltar espaço para a troca com o processo de cálculo, o Solidon calcula o passo mesmo assim e indica-o no relatório. Antes parava com o conselho de calcular de forma mais grosseira.

### Modelar, texto e esboço

- Com «Nas duas faces», «Aplicar texto» põe as letras também no verso, legíveis por fora. Serve para bandeiras, placas e etiquetas.
- As inscrições são compostas com mais precisão: as letras ficam no seu lugar e as curvas seguem a fonte, em vez de perder até 2 por cento de área em tamanhos pequenos.
- A simetria em «Modelar» espelha no centro do corpo, também longe do centro da mesa. Os projetos antigos mantêm a sua forma.
- O pincel de modelação atua só sobre a face virada para ele. Rebaixar uma placa fina já não empurra também a face de baixo.
- Um traço sobre o plano de simetria atua uma vez em vez de duas, e logo ao lado o traço e o seu reflexo fundem-se suavemente.
- O editor de esqueleto mostra ossos e articulação na vista, e uma articulação fica no meio do corpo em vez de na pele, assim a figura dobra de forma uniforme.
- A barra de modelação chama agora «Intensidade» ao valor do pincel, em vez de «Espessura», que fazia pensar numa parede.
- Se um traço de modelação fura a parede ou a deixa fina demais, o relatório e a exportação indicam-no, com «Mostrar o ponto» e «Desfazer o traço».
- Agora «Fundir suavemente» calcula fino também na janela, desde que o corpo não seja muito grande.
- Se um bloco como um buraco de fechadura passa a borda da sua face, mesmo que só com o escareamento ou o chanfro, ou entra numa parede atrás, o relatório indica-o.
- Uma medida escrita como comprimento 40 estica o esboço só nessa direção. O corpo resultante fica fechado e assente na mesa.
- Os desenhos SVG chegam corretos: rotações, inclinações, cantos arredondados, elipses e arcos elípticos estão certos, e as camadas ocultas ficam de fora.
- O destino de «Alinhar à característica» começa vazio, e o primeiro clique na vista preenche-o. «Aplicar» espera até lá em vez de pôr o corpo do lado errado.
- Um ficheiro em metros que também caberia na mesa lido em polegadas já não é lido mal sem aviso. O Solidon pergunta a unidade.
- Outro traço numa cavidade acabada de escavar torna-a mais funda, também com um pincel pequeno. Até agora não tinha efeito e contava como falhado.
- Em «Modelar», a janela mostra cada traço com a mesma rapidez, também depois de muitos traços, e as sessões grandes calculam a pré-visualização em segundo plano. Antes ficava mais lenta a cada traço.
- Com «Fixar o estado», o Solidon guarda uma sessão de modelação tão fina como a exportação e a impressão a calculam, e a janela continua utilizável. Antes guardava a vista mais grosseira.
- Um duplo clique em «Modelar» no histórico reabre a sessão com os seus traços. Ctrl+Z desfaz um traço inteiro, e «Concluído» altera o mesmo passo.
- A entrada «Criar a partir de um esboço …» começa logo a desenhar, o plano de desenho mostra a sua origem, e um duplo clique no histórico reabre um desenho no modo de desenho.
- Em «Modelar» e no editor de esqueleto, a barra mostra espessura de parede ou saliência como mapa com legenda e avisa de um traço fora do volume de impressão. Depois de dobrar, diz como imprime.
- Uma textura aplicada seleciona-se por inteiro. O painel de seleção oferece então «Alterar textura» e «Remover textura».
- O texto segue um arco ou contorna uma superfície arredondada, e «Incrustar texto» coloca-o à face na sua própria cor.

### Gerar com IA

- Cancelar durante «Mais uma tentativa» só para a tentativa em curso. As terminadas continuam disponíveis para escolher.
- Cada tentativa da lista indica a sua frase ou imagem e a semente. Se a sua entrada já não corresponder à tentativa escolhida, o diálogo diz qual será aplicada.
- Agora «Configurar modelo de imagem …» descarrega o modelo de imagem mesmo que os outros pesos já existam.
- Se um erro ao gerar indicar a configuração como saída, ela aparece como botão no diálogo.
- Enquanto um modelo é gerado, a janela continua utilizável. O diálogo afasta-se, e a barra de estado mostra progresso, tempo e «Cancelar».
- O diálogo de gerar indica o volume no tamanho com que a peça chega.
- Um modelo gerado desfaz-se com um único Ctrl+Z. Antes eram precisos três ou quatro.
- Se «Aplicar» for recusado ao gerar, o diálogo fica aberto com todas as tentativas e indica a saída, em vez de deitar fora a malha.

### Utilização e sistema

- No Mac, o Solidon já não fecha pouco depois de arrancar. Na versão 0.5.1 isto acontecia em todos os Mac, mesmo sem um rato 3D ligado.
- A caixa «Criar as medidas como parâmetros» vem marcada da primeira vez e depois lembra a sua última escolha, mesmo após reiniciar.
- Os diálogos abrem no tamanho do seu conteúdo, sem espaço vazio, e um tamanho que tenha ajustado mantém-se.
- A exportação, «Fatiar» e «Abrir no slicer …» recebem sempre o cálculo fino, não a vista mais grosseira da janela. Arredondamentos e cones chegam ao ficheiro com resolução completa.
- Uma exportação durante um cálculo em curso espera pelo resultado novo. Antes o ficheiro podia ainda levar a medida antiga.
- Se exportar só uma parte da cena, o diálogo de ficheiro e a confirmação indicam o âmbito, por exemplo «1 de 2 corpos».
- A barra de parâmetros recusa uma medida fora do seu limite em vez de deixar a vista vazia.
- Na barra de parâmetros cada passo de seta conta, e o foco fica no campo.
- Na barra de parâmetros as medidas de dois paralelepípedos levam o seu número, e uma medida com intervalo de trabalho próprio tem um cursor.
- Se um passo espera uma pergunta, «Aplicar» continua disponível e a pergunta aparece.
- No diálogo de uma operação as etiquetas ficam numa coluna, os campos têm a mesma largura e cada interruptor está antes do que comanda.
- As marcas nas listas leem-se em todas as linhas, e as cores aparecem como um ponto redondo ao lado.
- A paleta de comandos explica ferramentas e ações de ficheiro numa frase.
- Depois de mudar o parâmetro, «Gerar variantes» começa no valor desse parâmetro.
- Se a gravação de uma calibração falhar, os valores anteriores mantêm-se.
- No projeto de exemplo do segundo caminho, os furos dos parafusos seguem a largura e a espessura.
- A janela «Novidades» e o site mostram o realce como texto destacado em vez de asteriscos.
- Todas as traduções usam as mesmas palavras para características, botões e termos de impressão, e as mensagens seguem a pontuação de cada língua.
- O botão que desconta o consumo do inventário de filamentos chama-se agora «Deduzir», e as indicações nomeiam as ações como a janela, por exemplo «Uniformizar os triângulos».
- A forma de tratamento é uniforme: espanhol, português e francês usam a forma de cortesia, o italiano trata por tu. Foram corrigidas três mensagens em espanhol e português que diziam o contrário.
- Enquanto um diálogo mostra a pré-visualização, os espaços chegam a todos os campos de texto, também ao questionário e ao chat, e caixas e botões aceitam a barra de espaço.
- Ao «Escalar», um corpo fica assente na mesa em vez de se afundar sob a placa, e a vista volta a enquadrá-lo quando cresce.
- Algumas constatações que se referem a um passo abrem-no para alterar, por exemplo «Alterar tamanho» depois de «Escalar para a cota».
- Uma linha de resumo do relatório como «Reduzir para o volume de impressão» é um único passo de anular para todos os corpos.
- A ajuda de uma operação salta no manual diretamente para a sua entrada, e a referência nomeia campos e opções como aparecem no diálogo.
- Quando outros programas ocupam o computador, «Cancelar» para um cálculo longo em menos de um segundo, em vez de pedir um reinício após vários segundos.
- Um modelo de linguagem local pode dar doze passos em vez de oito por pedido no chat e resolve assim mais pedidos com várias partes.
- O painel de seleção volta a caber na sua coluna, e a coluna de medidas da árvore mostra a medida inteira, como «Ø5,19 mm» em vez de «…».
- Num furo, «Alterar característica» abre diretamente «Alterar furo» com pré-visualização, em vez de só remeter para ele.
- Ao clicar em «Aplicar» durante uma pré-visualização em curso, o Solidon calcula a alteração uma só vez. Antes calculava-a depois uma segunda vez.
- A vista de diferenças traceja o que foi acrescentado e o que foi removido em duas direções, para os distinguir também sem cor.
- Quando o Solidon pergunta a unidade de um ficheiro ao abrir, as medidas aparecem na sua unidade de exibição e com o separador decimal da sua língua.
- Se arrastar um ficheiro que o Solidon não abre, por exemplo do Blender, ele indica como o trazer como 3MF, STEP ou STL. O G-Code vai para «Verificar o G-Code».
- Pode abrir vários ficheiros num só passo. Mantêm a posição entre si, um Ctrl+Z desfá-los todos, e os avisos de importação iguais aparecem agrupados no relatório.
- Por cima do histórico, «Antes/depois» mostra com um cursor cada estado anterior. «Continuar aqui» insere ali passos novos, e os nomes dos seus passos mantêm-se.
- Com «para», «Deslocar» leva o centro, o centro da base, um canto ou uma característica a uma posição fixa, e «Rodar» leva o corpo a ângulos fixos, também com vários corpos.
- Se copiar a ligação da página de um modelo, ela já aparece no campo de «Modelo da internet», e o Solidon mostra o caminho pelo navegador.
- Se uma caixa de diálogo não pode aplicar, o motivo aparece também sob os seus campos, não só na faixa por cima da vista.
- Depois de Ctrl+Y, a linha de estado indica o passo refeito, como depois de Ctrl+Z.
- As miniaturas dos exemplos e dos blocos mostram a altura para cima. Até agora as peças altas apontavam nelas para baixo.
- Os exemplos incluídos abrem com a sua impressora e o seu material. Até agora eram calculados para a impressora genérica.
- Se o Solidon não conseguir guardar a opção «Incluir valores», o aviso aparece junto ao interruptor.
- Se outros programas ocuparem todos os núcleos no Windows, um cálculo num modelo grande já não fica parado durante minutos.
- Os comprimentos nas mensagens usam o separador decimal do seu idioma.
- Depois de carregar um modelo grande, o indicador de carregamento fica até a vista mostrar o modelo.
- Um clique numa linha do relatório de verificação seleciona os seus corpos mesmo que a lista se desloque durante o clique.
- Os números fixos ligam-se com um clique a uma medida do projeto, e o seletor de mesas indica os corpos de cada mesa e mostra inteira a escolhida.

## 0.5.1

### Imprimir e entregar ao slicer

- No PrusaSlicer, ElegooSlicer, Bambu Studio, Creality Print e OrcaSlicer vale o perfil do fabricante. O Solidon só escreve o que altera ou aceita das sugestões.
- O nível «Padrão» imprime com as velocidades e acelerações do perfil do fabricante em vez de travar cada impressora a 40 mm/s. Numa Centauri Carbon 2, as peças grandes levam 40 a 50 % menos tempo.
- As sugestões aplicadas valem só para a peça que precisa delas: suportes, brim e os valores de um ajuste, em cada slicer suportado. As definições de impressão indicam as peças.
- Se uma peça se imprime de pé sem suportes, «Orientar para impressão» deixa-a de pé em vez de a deitar sobre suportes. Um conjunto de minigolfe de 16 peças cabe assim numa placa em vez de quatro.
- Se uma peça não cabe na mesa em nenhuma posição, as definições de impressão dizem já antes de fatiar em quanto é demasiado grande e oferecem «Dividir o modelo» e «Reduzir para o volume de impressão».
- Mesmo onde as partes de um modelo apenas se tocam, «Dividir o modelo» funciona, e os conectores ficam bem orientados nos seus furos em cada junta. Antes o relatório indicava colisões.
- O Solidon usa o ângulo de saliência do perfil do fabricante da sua impressora: 60 em vez de 45 graus na Elegoo, Bambu e Creality. Chanfros e inclinações suaves já não recebem suportes desnecessários.
- Em paredes exteriores redondas, o Solidon propõe uma «Costura em bisel», em cada slicer suportado. A impressão demora assim 2 a 4 % mais.
- Se o seu slicer calcula o brim sozinho, como o ElegooSlicer, o Bambu Studio, o Creality Print e o OrcaSlicer, o Solidon não propõe um próprio. O do slicer dá mais borda às peças altas.
- Os níveis «Fino», «Rascunho» e «Resistente» escolhem agora o processo correspondente do seu slicer, por exemplo «0.12mm Fine» em «Fino».
- As definições de impressão mostram o que é impresso: a base é o perfil do fabricante, e os seus próprios valores ficam marcados e podem ser repostos um a um.
- A placa de impressão escolhe-se nas definições de impressão, e a temperatura da mesa acompanha-a. Se o fabricante não autoriza a placa para o seu filamento, o Solidon avisa antes.
- Sem «Aplicar as sugestões», nenhuma peça recebe mais um brim sem pedir, nem na exportação nem na entrega ao slicer.
- Nova sugestão «Manter os canais livres»: aplicada, a entrega bloqueia os suportes nos canais em cada slicer suportado. A janela do Cura recebe também o bloqueio e os valores por peça.
- Um teto sobre um canal de água ou um túnel já não atrai suportes para o modelo. Se mais nada precisar deles sobre o modelo, o Solidon propõe-nos só a partir da mesa.
- As definições de impressão mostram as sugestões mais depressa: no suporte de berbequim, ao fim de 4,3 segundos em vez de 7,6.
- Os projetos da 0.5.0 imprimem com a velocidade da sua impressora. O que tinha definido neles mantém-se.
- A velocidade da primeira camada vale agora também para o seu enchimento. Antes, o slicer fazia o fundo à velocidade do fabricante, 105 mm/s na Centauri Carbon 2.
- Com o PrusaSlicer, a impressão começa agora como na própria Prusa: com nivelamento da mesa, linha de purga e verificação da impressora.
- O PETG vai agora para o PrusaSlicer como PETG, já não como PLA.
- No OrcaSlicer, cada impressora recebe pré-selecionada a sua própria máquina e o processo padrão: a Sovol SV06 já não recebe a versão High-Speed, nem a Ender-3 V3 «0.12mm Fine».
- Novas: as Creality Ender-3 V3 SE e V3 KE. Até agora, uma SE recebia os valores da muito mais rápida Ender-3 V3.
- As cópias iguais são calculadas uma só vez por «Orientar para impressão», que termina o mesmo conjunto de minigolfe em menos de um terço do tempo.
- Os níveis de qualidade da janela de impressão aparecem agora no idioma da interface.
- A velocidade dos percursos em vazio também vem da impressora: a Centauri Carbon 2 desloca-se a 500 em vez de 150 mm/s, como no próprio perfil da Elegoo.
- Se mediu a saliência da sua impressora, também o slicer só coloca suportes a partir desse ângulo, enquanto valerem a altura de camada e a largura do cordão da medição.
- Também o relatório calcula agora as saliências com o ângulo a partir do qual o seu perfil do slicer coloca suportes.
- Se um brim, skirt ou raft ultrapassa a mesa, o Solidon avisa na passagem para o slicer e oferece «Dispor na mesa».
- Se o slicer recusa uma peça demasiado alta, o Solidon indica as duas alturas e oferece «Dividir o modelo», «Reduzir para o volume de impressão» ou outra impressora.
- Se o slicer recusa uma peça que não cabe na sua placa, o Solidon indica o motivo e oferece «Dividir o modelo», «Reduzir para o volume de impressão» e «Dispor na mesa».
- Se o Bambu Studio fica parado depois de fatiar, o Solidon aproveita o ficheiro de impressão terminado em vez de dar erro ao fim de cinco minutos.
- Com o Cura também se fatiam modelos grandes. Antes o processo terminava sem ficheiro de impressão, por exemplo na torre Eiffel com 313 000 triângulos.
- Se o Creality Print só consegue fatiar um 3MF na sua janela, o Solidon diz isso e leva a «Abrir no slicer …».
- Se a primeira camada tem passagens estreitas, mesmo poucas e longas numa peça grande, o Solidon propõe fazê-la a 50 mm/s. Assim as linhas curtas aderem melhor.
- O Solidon só propõe um «Tempo mínimo por camada» mais longo onde o seu perfil não tem nenhum. Antes, a sugestão aparecia em quase todas as peças com chanfro ou ponta.
- Onde o seu slicer já limita a velocidade pelo caudal volumétrico, o Solidon deixa de propor um limite de velocidade próprio.
- Se adotar os valores de um perfil de filamento e depois mudar de filamento, voltam a valer os valores do novo.
- A primeira camada imprime agora linhas tão largas como o perfil da sua impressora, normalmente 0,5 mm com bico de 0,4. Com o Cura, a cabeça já não anda a passo de caracol entre elas.
- Com o Cura, a impressão começa agora com o código de início da sua impressora, como no fabricante. Se o Cura não conhece a impressora ou o código falta no ficheiro, o Solidon avisa.
- Com o Cura, a primeira camada usa agora a aceleração do perfil do fabricante em vez da aceleração de impressão total.
- Os suportes do Cura seguem agora o padrão dos perfis de fábrica: ligados, com um teto leve e velocidade moderada.
- Com o Cura, as paredes em saliência imprimem agora mais devagar, como no fabricante. Impressões com muitas saliências demoram até cerca de 20 % mais.
- Com o Cura, o enchimento imprime agora depois das paredes, e as deslocações evitam os suportes e recolhem o filamento em percursos longos.
- O perfil para a janela do Cura corresponde agora à impressora configurada no Cura. Antes, o Cura rejeitava-o em algumas impressoras ou não o mostrava.
- As definições de impressão já não oferecem o caudal volumétrico para o Cura, porque o Cura não o lê.
- Os suportes em grelha chegam ao slicer como grelha verdadeira, com a direção a mudar em cada camada, em vez de linhas soltas que se deslocam na impressão.
- Quando uma peça assenta em muitos pés pequenos, o Solidon propõe um brim onde o seu slicer não calcula um próprio, mesmo que os pés juntos tenham área suficiente.
- Uma faixa estreita e inclinada junto à parede exterior já não conta no relatório como uma ponte longa.
- Um letreiro que é uma peça própria encostada a uma parede já não começa no ar segundo o relatório, e o Solidon já não propõe suportes para ele.
- O relatório só mostra o aviso para calibrar as tolerâncias do seu material em modelos com ajustes. Só aí o Solidon as usa.
- A entrega ao Cura transfere as primeiras camadas sem ventoinha como arranque gradual. Só avisa quando o ficheiro de impressão final difere de facto.
- Depois de «Reduzir para o volume de impressão», a peça continua assente na mesa. Antes levantava-se, e o relatório dava-a como flutuante.
- Se uma peça só cabe na mesa com uma margem mais estreita, «Dispor na mesa» coloca-a no centro em vez de ultrapassar a borda, e o relatório indica essa margem.
- Em modelos grandes, «Dividir o modelo» encontra a costura até duas vezes mais depressa, e nos modelos multicor numa fração do tempo. A divisão funciona como antes.
- Quando o Solidon divide automaticamente um modelo em três ou mais peças, os nomes são numerados e indicam os conectores, por exemplo «Calha de parede 2 de 3 · Pinos e furos».
- Um parafuso, uma porca ou um vedante impressos do catálogo de blocos já não contam no relatório como um corpo fragmentado. É uma peça própria, e isso é intencional.
- Os parafusos e porcas impressos têm folga também na cabeça e no apoio, e continuam desmontáveis mesmo impressos junto com a peça. Os projetos antigos avisam da alteração ao abrir.
- Com um parafuso de cabeça escareada do catálogo de blocos, um corpo feito de faces e arestas mantém-se estanque ao exportar: a peça e o parafuso entram no ficheiro cada um fechado.

### Editar furos

- Um furo com escareamento de um lado e chanfro do outro pode ser inclinado, deslocado e duplicado. Antes, o Solidon recusava.
- Um furo ou escareamento inclinado já não corta o que está à frente da sua boca, como uma nervura ou o favo ao lado.
- Um furo escareado numa face curva pode ser deslocado, também com um clique na vista. Depois de deslocado, inclinado ou removido, o local antigo fica rente com a face.
- Um furo escareado com a aresta da boca arredondada numa face plana pode ser deslocado, duplicado e removido juntamente com o arredondamento. Antes ficava uma depressão.
- Furos cegos, furos oblongos e alargamentos numa face inclinada, e furos cegos inclinados como um alojamento de íman sem lábio, ficam totalmente abertos na boca. Antes ficava ali uma película.
- Deslocar e duplicar avisam quando a parede até ao furo vizinho fica demasiado fina ou se rompe.
- Se um furo sai pela lateral da peça depois de deslocado, duplicado ou inclinado, o Solidon indica-o também em zonas com degraus. Uma cópia que não foi criada é detetada.
- Um furo deslocado ou duplicado de um ficheiro STL já não avisa por engano, em placas finas, que deixou de ser passante.
- Em nervuras e favos, um furo inclinado já não indica por engano que passa do bordo.
- Depois de deslocar, inclinar ou duplicar, o painel de características mostra as cotas que o resultado tem de facto.
- Furar, deslocar, «Alterar furo» e esticar para furo oblongo deixam o modelo fora do furo tal como estava. O reconhecimento a seguir termina muito mais depressa em modelos grandes.
- Se num corpo feito de faces e arestas, por exemplo de um ficheiro STEP, um corte de furo falha sem se notar, o Solidon deteta-o e volta a calcular. Antes podia ficar um corpo danificado.
- Em corpos feitos de faces e arestas, os passos de furo ficam prontos em segundos: numa placa perfurada de um ficheiro STEP, «Alterar furo» demora 2 em vez de cerca de 120 segundos.
- Em corpos feitos de faces e arestas, «Cortar bolsa» já não devolve um corpo com defeito.
- Um furo oblongo pode ser encurtado. Puxado até à sua própria largura, volta a ser um furo redondo.
- A pega na ponta de um furo oblongo agarra-se em qualquer ponto da abertura, e já não salta para o ponteiro no primeiro arrasto.
- Os furos oblongos levam consigo os chanfros e a boca oblíqua ao serem deslocados ou duplicados. Antes, os chanfros ficavam no local antigo.
- Um alojamento de íman do catálogo de blocos pode ser deslocado, duplicado, multiplicado e removido, juntamente com o lábio que segura o íman.
- Num alojamento de íman, «Alterar furo» com «Incluir escareamento, degraus e estreitamento» muda o diâmetro com o lábio. «Apenas o diâmetro do furo» mantém a abertura e avisa se ficar apertada.
- Colocada em ângulo com a face, a abertura de um alojamento de íman, de um furo para parafuso ou de um assento de rolamento fica livre. Antes havia uma cunha de material por cima.
- Se um alojamento de íman ou uma suspensão em buraco de fechadura fica inclinado em relação à face, o Solidon avisa que o lábio só segura de um lado e oferece «Corrigir a entrada».
- Se um bloco como um alojamento de íman não remove nada no ponto escolhido, o Solidon avisa e aconselha clicar na face.
- Num alojamento de íman com lábio, «Esticar para furo oblongo» também recusa em corpos feitos de faces e arestas, em vez de cortar o lábio.
- Se colocar uma rosca, uma bucha de inserção a quente ou um alojamento de porca num furo, a janela indica em cima o tamanho que encaixa e pré-seleciona exatamente esse.
- Num escareamento, «Alterar elemento» corta a nova medida como se tivesse sido escareado logo assim. Antes, o Solidon recusava ou deixava uma película fina atravessada sobre o furo.
- Quando peças de um modelo estão metidas umas nas outras, o Solidon une-as antes de calcular, tal como serão impressas. Volume e furos batem certo, e o relatório di-lo.
- Quando alarga um furo, a pré-visualização precisa mostra todo o material removido, também em modelos grandes, com um corte de vista e em corpos com canais fechados.
- Ao escrever uma cota numa figura grande, a pré-visualização grosseira aparece em menos de um segundo em vez de até dezanove, e a de um furo nela resulta.
- Se um passo num modelo aberto só calcula de forma aproximada e o volume cresce, o relatório indica o desvio e oferece «Reparar primeiro e voltar a calcular».

### Arredondar e chanfrar

- A escolha de arestas «Horizontal», «Em cima» ou «Em baixo» já não inclui o bordo de um furo lateral. Se o quiser, escolha-o à parte; os projetos antigos calculam como foram guardados.
- Num modelo importado, o bordo de um furo é arredondado ou chanfrado tão fundo como numa peça construída. Antes, com raios grandes, o arredondamento ficava até um quinto mais raso.
- Se a cota não cabe em todas as arestas de uma escolha como «Todos» ou «Vertical», o Solidon trabalha as que cabem e mostra as outras com «Mostrar o ponto», em vez de recusar.

### Cotas na vista

- De furo em furo, as cotas na vista aparecem num terço do tempo. O primeiro clique numa característica já não congela a janela, mesmo em modelos grandes.
- Um clique num furo já não mostra imagens intermédias: o painel de seleção e o cartão de cotas aparecem logo no seu lugar, sem saltar.
- Um clique nas setas de um furo selecionado já não mantém a seleção presa: o furo seguinte pode ser clicado como habitualmente.
- Escape nas cotas da vista descarta o rascunho e retira a seleção, como «Cancelar».
- Um clique em «Aplicar» já não se perde em silêncio, e as cotas que não escreveu ficam exatamente como foram medidas.
- Um furo começado já não se perde pelo caminho: um clique no relatório, uma troca de ferramenta ou Ctrl+Z pedem primeiro para o aplicar ou cancelar.
- Ao escrever uma coordenada, os campos de cota já não desaparecem depois do segundo algarismo.
- Em modelos grandes, «Medir a espessura de parede» responde cerca de quatro vezes mais depressa.
- Um clique no centro de um furo escareado seleciona o furo e não o escareamento, e as cotas indicam a aresta pelo lado, como «Aresta exterior à esquerda» em vez de «Aresta exterior 4».
- Com uma aresta ou uma distância selecionada, o painel de seleção já não diz «Nenhum detalhe selecionado …».

### Reconhecimento

- As características são reconhecidas sozinhas até 1,5 milhões de triângulos. Até cinco milhões, o Solidon pergunta antes e indica a memória necessária e a duração no seu computador.
- Recusado o reconhecimento completo, recupera-se com «Reconhecer todas as características» no relatório ou na linha de comandos. Se demorar, «Carregar sem reconhecimento de características» salta-o.
- Em modelos grandes, «Detetar elementos num local» encontra faces onde antes indicava triângulos a mais. O local também se escolhe com o teclado.
- Em modelos grandes, «Detetar elementos num local» começa logo a procurar. Antes recalculava primeiro o modelo todo, 40 segundos por tentativa no dragão do mausoléu.
- Modelos grandes e grelhas são reconhecidos muito mais depressa: uma cama de casa de bonecas gerada, com 1,2 milhões de triângulos, em 27 segundos em vez de 174. Cancelar atua em poucos segundos.
- As cópias e as peças rodadas ou deslocadas herdam as características do original em vez de as procurarem de novo. Um projeto com muitas peças iguais é calculado assim em menos de metade do tempo.
- Depois de um furo, a face de um corpo construído indica o seu tamanho atual, e um furo novo já não falta na árvore quando antes se alterou outro.
- Letreiros e escoras aparecem na árvore como lados arredondados em vez de dezenas de arredondamentos com raios variáveis.
- Os contornos feitos de arcos e retas são reconhecidos arco a arco com o seu raio. «Converter em faces e arestas» fica assim muito mais rápido.
- Um pino escalonado já não conta como rosca. Voltam os cilindros e furos que essa confusão tinha engolido.
- O lábio de um alojamento de íman chama-se estreitamento na árvore e nomeia a sua abertura. Nenhuma ação o transforma mais num escareamento.
- Depois de «Refinar as arestas», o Solidon reconhece arredondamentos, furos e letreiros como no original, mesmo após outro furo. Arredondamentos iguais mantêm o nome, também após «Deslocar».
- Um padrão à volta de uma pega redonda, como um recartilhado numa tampa, mantém o centro e a direção ao continuar a editar.
- Depois de «Dividir» e «Cortar fora», uma face dividida mantém o nome na peça maior, e os ajustes nela continuam válidos.
- Se clicar na aresta de bordo de um furo deitado, ela chama-se «Vertical», tal como está realmente.
- Se um modelo tem mais de 5 000 características, o Solidon mantém as maiores em vez de ficar sem nenhuma. Escalar não baralha os seus nomes.
- Um bloco com uma só característica tem na árvore o mesmo nome que no histórico, como «Alojamento de íman» em vez de «Furo cego 1».

### Importar e reparar

- Um modelo grande aparece na vista logo depois de importado, e as suas características vêm a seguir. Antes só aparecia quando o reconhecimento terminava.
- Um 3MF com várias placas do Bambu Studio, OrcaSlicer ou ElegooSlicer põe cada peça na sua placa, no seu lugar. Antes iam todas para uma, muitas fora da mesa.
- Um 3MF com várias placas acrescentado a um projeto mantém as suas placas e coloca-as a seguir às existentes.
- Um modelo adicional vai para o primeiro lugar livre das placas, ou para uma placa nova, e fica lá. Antes mantinha as coordenadas do seu ficheiro, quase sempre fora da mesa.
- Também um modelo de «Gerar modelo» fica pousado na mesa, no primeiro lugar livre das placas.
- Um modelo sem cores próprias mantém a cor do corpo depois de fechados os seus furos. Antes ficava cinzento, e «Converter a textura em filamentos» fazia dele um filamento cinzento.
- Se faltar a um modelo um pedaço de parede de furo ou parte de um cone de escareamento, o Solidon fecha a lacuna como parede, não como tampa atravessada no furo.
- As costuras abertas fecham-se ao importar e reparar sem unir peças que apenas se tocam. Um modelo intacto fica inalterado.
- As sobreposições são agora resolvidas pelo próprio «Reparar». Quando as peças de um modelo importado estão metidas umas nas outras, o relatório oferece «Resolver as sobreposições».
- Uma superfície sem espessura fica aberta e oferece «Dar espessura». Uma abertura grande indica o seu local com «Mostrar o ponto», e «Deixar aberto» deixa aberta só essa.
- Depois de fechar uma abertura ao importar, «Mostrar o ponto» contorna toda a face nova com uma cor própria.
- Uma peça virada do avesso ao lado de um corpo oco é endireitada sem perder a cavidade. Uma peça dentro do material de outra é indicada em vez de adivinhada.
- O relatório depois de importar é mais curto: as constatações que o resultado desmente desaparecem, e onde se pode agir há um botão em vez de um conselho.
- O mapa de defeitos de malha mostra as zonas sãs na cor do corpo, para que cada defeito sobressaia, e traz «Reparar» na legenda. Se houver um só corpo, seleciona-o sozinho.
- A procura de sobreposições chega agora ao fim também em modelos com leques de triângulos estreitos. Mapa de defeitos e reparação veem então o modelo inteiro.
- Um 3MF do PrusaSlicer já não carrega modificadores, bloqueadores e reforços de suportes como material maciço. Um volume negativo é subtraído da peça.
- Com «Refinar as arestas» mantêm-se todas as características e surgem até quatro vezes menos triângulos: um suporte de berbequim com arestas de 1 mm em cinco segundos em vez de catorze minutos.
- Um modelo fechado continua estanque e conserva as cores de filamento. Com triângulos a mais, o Solidon indica um comprimento de aresta que funciona de facto.
- A pré-visualização de «Refinar as arestas» e «Reduzir triângulos» fica pronta em segundos em vez de congelar a janela, e um comprimento demasiado fino é recusado de imediato.
- Se um modelo for demasiado fino para «Refinar as arestas», o relatório oferece «Reduzir triângulos e tentar de novo» com um número que realmente resulta.
- Se «Suavizar» fosse virar um corpo do avesso, o Solidon avisa e oferece «Refinar as arestas e tentar de novo» com um comprimento de aresta que resulta.
- Os conjuntos grandes importam mais depressa: a reparação ao importar um navio pirata com 1,2 milhões de triângulos demora cerca de 30 % menos tempo.
- Ao abrir ficheiros 3MF grandes, a janela continua utilizável, também enquanto o modelo é lido.
- Se importar uma cópia com outro nome de um ficheiro já aberto, o corpo leva o nome novo. Antes chamava-se como o primeiro ficheiro.
- Em malhas grandes, «Fechar superfície aberta» calcula em segundos: 1,8 em vez de 24 segundos com 122 752 triângulos.

### Manual e site

- Quinze guias mostram passo a passo, com imagens da aplicação, como verificar, imprimir e reparar um modelo, construir e dividir uma peça, aplicar-lhe texto ou imprimir a duas cores.
- O manual começa em «Por onde começo?» e leva daí a cada guia. F1 na caixa de diálogo de uma operação abre o seu guia ou a sua entrada.
- Uma imagem de conjunto explica a janela: cada número na imagem indica uma área.
- A pesquisa do manual encontra a página certa também com palavras do dia a dia, mostra-a primeiro e abre-a onde a palavra aparece.
- A referência indica, para cada operação, onde encontrá-la no menu ou no painel de seleção.
- As páginas explicativas são um terço mais curtas. Se houver um guia em imagens sobre o seu tema, a ligação aparece no fim da página.
- No site e no PDF, o manual está organizado como na aplicação, dos primeiros passos à consulta. No PDF, os marcadores levam a cada capítulo.

### Utilização e sistema

- Os cálculos grandes, como a pré-visualização ou «Refinar as arestas», correm num processo à parte: a janela continua utilizável e «Cancelar» atua logo. Para isso corre um segundo processo do Solidon.
- Ao carregar e em cálculos longos, um relógio conta o tempo decorrido mesmo com o progresso parado, e o tempo restante já não salta quando começa uma nova parte do cálculo.
- A cópia de segurança automática corre em segundo plano e já não bloqueia a janela, nem com modelos grandes. Se não puder ser escrita, o Solidon avisa.
- Um modelo numa unidade lenta ou que não responde já não congela a janela ao abrir.
- Se um ficheiro de «Abertos recentemente» tiver sido movido, o Solidon di-lo e oferece «Escolher outro ficheiro».
- Um ficheiro que não foi possível ler já não vai parar a «Abertos recentemente», e o ficheiro seguinte já não anuncia o nome dele ao carregar.
- Um ficheiro sem modelo legível já não fica como primeiro passo, no qual cada ficheiro seguinte falhava com «A cadeia para».
- Os projetos abertos recentemente na página inicial abrem com um clique.
- Sem nada selecionado, o painel de seleção oferece o que se aplica a todos os corpos: «Orientar para impressão», «Dispor na mesa» e «Verificar sobreposições».
- Depois de «Dividir o modelo», todas as peças ficam completamente à vista.
- Cada passo interrompido no relatório tem um botão: «Corrigir a entrada» abre-o com o cursor no campo afetado.
- Depois de «Dividir o modelo», o relatório diz numa frase que as peças continuam encostadas, em vez de em mais de vinte linhas, e as linhas do corpo antigo já não têm botões vazios.
- Um desenho traçado livremente sem cota já não gera um aviso no relatório.
- Se o relatório só tem notas, diz em cima «Pronta para imprimir», e uma nota de configuração já não fica pré-selecionada como um aviso.
- Os avisos do relatório têm um botão: «Mostrar o elemento» num ajuste que não encaixa, «Abrir as definições de impressão» em avisos de mesa, suportes, bico e brim.
- Um relatório de erro indica as pastas na sua pasta de utilizador sem o seu nome de utilizador, mesmo quando o próprio Solidon está aí instalado.
- Em «Primeiros passos», a impressora do seu slicer aparece logo ao abrir. Antes a sugestão só chegava ao fim de alguns segundos, e «Concluído» ficava até lá com a impressora genérica.
- Depois de importar, a barra de título tem o nome do modelo em vez de «Sem título», e «Primeiros passos» indica os slicers pelo nome e não pelo nome do ficheiro.
- O slicer escolhe-se nas definições de impressão por cima dos perfis, mesmo com essa secção recolhida.
- A impressora escolhida nas definições de impressão passa também para o próximo projeto novo. Se o seu slicer estiver noutra impressora, as definições oferecem-na com um clique.
- Se escolher outra impressora ou outro slicer, o perfil de máquina memorizado do anterior deixa de valer.
- Na barra de parâmetros e na janela de uma operação, um número escrito fora dos limites é recusado em vez de ser cortado em silêncio, e o Solidon indica o limite.
- A pergunta antes de apagar um passo indica os passos dependentes que vão com ele.
- O histórico indica um parâmetro alterado pela sua etiqueta e mostra o valor antes e depois.
- A pega de uma face selecionada mostra só a seta com que a desloca.
- Sem texto, «Aplicar texto» diz que falta o texto em vez de dar a pré-visualização como indisponível.
- Depois de desenhar, volta à direita o separador de antes, por exemplo o relatório. Até agora aparecia o chat, e «Entregar ao slicer …» ficava tapado.
- A «Paleta de comandos …» encontra operações em cada língua também com palavras do dia a dia, como «copy» ou «calamita». Até agora só conhecia essas palavras em alemão.
- Ao guardar com «Guardar a seleção como bloco …», o Solidon verifica a espessura das paredes do bloco muitas vezes mais depressa.
- Em todas as traduções, «Separar» e «Dividir» têm agora nomes diferentes, as teclas os do teclado, e a interface italiana trata por tu em todo o lado.

### Assistente com modelo local

- A escolha do modelo recomenda também um modelo mais pequeno para placas a partir de 10 GB de memória gráfica e indica para cada um a memória que ocupa e como resolve pedidos com várias partes.
- O assistente recebe em detalhe só as ações que servem o pedido. Fica assim espaço para o histórico e a resposta, e os pedidos resultam muito mais vezes.
- O modelo local fica carregado três minutos depois de uma resposta, e a pergunta seguinte já não espera pelo arranque.
- Uma resposta que não encontra fim é interrompida após um comprimento fixo e indicada como cortada, em vez de ocupar a placa gráfica até ao limite de dez minutos.

## 0.5.0

### Reconhecimento

- O reconhecimento em modelos importados é muitas vezes mais rápido: uma placa com 200 000 triângulos e os seus furos fica pronta num segundo, onde uma forma livre lisa demorava minutos.
- Faces pequenas como a ponta de um came, furos cortados e chanfros de boca são reconhecidos da mesma forma numa malha e num corpo exato.
- Cavidades fechadas e câmaras de ar encaixadas são reconhecidas como um todo. Um furo que dá para uma cavidade já não aparece como fantasma.
- Roscas importadas são medidas: passo, número de entradas, sentido direito ou esquerdo e diâmetro nominal. Peças espelhadas mantêm o sentido correto.
- Cones, esferas e anéis mantêm as suas medidas reais, e o painel de características diz de onde vem um valor: medido, ajustado ou do passo.
- Uma peça espelhada, escalada ou repetida em padrão leva consigo as suas características. Características desatualizadas já não ficam ao lado das novas.
- Ficheiros STEP com superfícies de forma livre mantêm os furos editáveis, mesmo depois de guardar, reabrir e anular.
- Após uma alteração, cada característica que ainda existe mantém o seu nome. Se duas candidatas entram em questão, o Solidon pergunta em vez de adivinhar.
- Um clique num furo de um modelo com 360 000 triângulos responde num quarto do tempo.
- Um escareado que toca dois furos oblongos por igual continua a ser uma face cónica em vez de desaparecer num deles.
- Se um modelo é composto por várias cascas e não se consegue ler com segurança se alguma prende ar, o relatório di-lo como aviso.
- Um modelo fechado liberta a sua memória; antes ficavam algumas centenas de megabytes por modelo.
- Um modelo com muitas faces pequenas, como um padrão em favo de mel, mantém os seus furos e arredondamentos. Antes não mostrava uma única característica.
- Um campo de 1400 saliências é reconhecido em quatro segundos em vez de doze.

### Padrões

- Um favo de mel, um recartilhado, nervuras, ondas ou saliências aparecem na árvore como um padrão com passo, largura de célula e profundidade — também à volta de um punho. Antes eram centenas de faces.
- Um padrão remove-se com um clique ou volta a pôr-se com novo passo, largura de célula e profundidade. As células ficam onde estavam.
- Uma textura à volta de um cilindro segue a curvatura: as ranhuras têm a mesma profundidade, e um padrão à volta de toda a circunferência fecha sem costura. O passo passa para o valor que fecha.

### Desenho

- Desenhar numa peça escolhida mostra apenas essa peça na vista; as restantes ficam ocultas até «Mostrar vizinhas» as trazer de volta.
- Extrudir numa face escolhida agora anexa o novo corpo em vez de parar — antes nunca passava do esboço.
- Uma cavidade corta onde a desenhou, mesmo quando a face não está centrada na peça.
- Arredondar e chanfrar um retângulo cotado deixa as suas cotas inalteradas.
- Se desenhar com várias peças escolhidas, o Solidon pergunta em qual; o destino pode ser trocado a qualquer momento na barra.
- Escape já não descarta um esboço que começou.
- Um esboço já extrudido pode ser reutilizado para a próxima cavidade, sem o desenhar de novo.
- Um clique numa face oferece diretamente «Desenhar aqui» e «Desenhar furo ou recorte».

### Editar no modelo exato

- Os corpos básicos são sempre criados com faces e arestas reais. A opção «Editar faces e arestas mais tarde» desapareceu; projetos antigos calculam-se sem alterações.
- Furo, furo oblongo, rebaixo, pino, cúpula e tronco de cone mantêm-se exatos num corpo exato quando os desloca, duplica, roda ou remove.
- Cordões e gargantas podem ser deslocados, duplicados, rodados, alterados e removidos. Uma rosca pode ser alterada e fechada.
- Uma rosca recebe a sua contraparte na outra peça com um só clique, na medida da tabela e como um único ajuste.
- Todos os blocos da biblioteca constroem-se exatamente num corpo exato, da união aparafusada à ranhura de vedação.
- Após uma mudança de raio, o Solidon arredonda a aresta certa, mesmo quando dois arredondamentos estão próximos.
- Se duas arestas estão no mesmo sítio, o Solidon pergunta qual pretende em vez de escolher uma.
- Aplicar espera até a pré-visualização mostrar o resultado atual. Um clique numa imagem desatualizada não escreve nada de errado.
- As cores de filamento mantêm-se nos corpos exatos e acompanham cada nova malha.
- Volume e área de um corpo exato chegam em milissegundos em vez de segundos.
- Inserir uma rosca demorou entre 0,38 e 0,41 segundos durante a medição, em vez de 8 a 13 segundos. A operação completa criou um perno roscado M6 × 1 com 12 mm de comprimento em 0,55 segundos.
- Unir, Subtrair e Pousar na mesa já não perguntam se devem converter corpos exatos. Continuam exatos.
- Ao deslocar um furo não ficam triângulos a mais no sítio antigo, e um escareado escondido não perde nada do seu volume.
- Reparar deixa um modelo limpo inalterado, também no corpo exato.
- A contraparte de uma rosca é construída em segundo plano. Entretanto a janela continua utilizável.

### Furar e cotas na vista

- Um furo clicado mostra logo as suas cotas na vista: distâncias às arestas, centro e diâmetro, com campos numéricos para escrever.
- Os campos de cota ficam ao lado da peça em vez de em cima dela, e as suas linhas não se cruzam.
- A referência de uma cota, aresta, centro ou eixo, muda-se com clique direito na cota ou com um clique no modelo.
- O que está na vista não se repete à direita no painel de seleção.
- Depois de puxar um furo até ficar oblongo, as cotas mantêm-se, mesmo que rode a vista. Os botões para puxar estão sempre no furo escolhido.
- Ao escolher um furo, a vista 3D podia falhar em algumas placas gráficas. Está corrigido.
- Um arrasto na pega sobrevive a um redesenho a meio do arrasto, e um passo da roda sobre um campo de cota amplia a vista em vez de alterar a cota.
- O primeiro Escape ao escolher uma referência retira apenas a escolha; os valores digitados mantêm-se.
- Com «Levar escareado e degraus», o furo também se desloca através das cotas. Haste e escareado movem-se juntos, num só passo.
- Se o Solidon recusar uma cota, o motivo aparece sobre a pré-visualização em vez de apenas «não foi possível calcular».
- Os campos de cota ficam onde estavam quando altera um valor. A cota em cujo campo escreve acende-se na vista.
- Os botões para o furo oblongo também funcionam enquanto as cotas do furo estão na vista: Aplicar puxa então o furo oblongo — com um diâmetro novo ao lado num só passo, na nova largura.

### Histórico

- No histórico já se pode inserir um novo passo antes de um existente, não apenas acrescentá-lo ao fim.
- Um passo do histórico arrasta-se com o rato para outro lugar, ou move-se linha a linha.
- Um passo pode ser desligado e voltado a ligar mais tarde sem o apagar; os passos dependentes ficam em repouso com ele.
- Se um passo posterior faz referência a uma característica que a reorganização renomeou, o Solidon segue-a e comunica-o.
- Se reorganizar o histórico fosse parar um passo posterior, o Solidon recusa e não muda nada.

### Verificar e imprimir

- As impressoras de resina chegaram: dois aparelhos genéricos por volume de impressão estão na lista, e uma própria cria-se com tamanho do píxel e parede mínima.
- Um projeto de resina já não recebe conselhos sobre bico, brim ou pontes, e a parede mínima vem do perfil da impressora.
- O ficheiro abre-se em qualquer programa, também no slicer de um fabricante de resina cujas definições o Solidon não conhece.
- Os corpos exatos são malhados tão finos quanto os píxeis de uma impressora de resina exigem; o relatório indica a medida.
- Os ajustes verificam os corpos reais na sua posição de montagem. A exportação pode ser cancelada antes.
- O desvio de forma mostra que faces de uma malha estão a que distância do original.
- Quando uma espessura de parede se estreita em cunha, o Solidon diz-o e aconselha imprimir primeiro a parede exterior.
- A procura de orientação assenta uma grelha de bordo estreito sobre o seu bordo, e uma grelha de travessas curtas não precisa de suportes.
- A ficha para o assistente diz sobre o ponto escolhido o mesmo que o painel de características.
- O desvio de forma de uma caixa com tampa calcula-se num décimo de segundo em vez de doze.
- Peças separadas para imprimir deixam de receber um aviso sobre a posição de montagem. O ajuste comunica apenas o que mediu.
- A procura de orientação num modelo com mais de um milhão de triângulos demora cinco segundos em vez de meio minuto.
- Distâncias muito pequenas aparecem no mapa de análise como decimais, não como potências de dez.
- O desvio de forma em arredondamentos e anéis é tão preciso como em planos e cilindros, e o mapa é calculado mais depressa do que antes.
- A ventoinha da peça volta a seguir a curva do perfil da impressora, em vez de girar à velocidade máxima em cada camada.

### Importar

- Um conjunto importado pode ser assente na mesa como um todo com um clique. As peças mantêm a sua posição relativa.
- Um glTF sem um tamanho plausível já não é tomado como metros. O Solidon pergunta a unidade e mostra as medidas para cada leitura.
- Um modelo com zonas abertas é fechado ao ser lido em vez de apenas comunicado: buracos na malha, faces invertidas, arestas com três faces. As aberturas grandes são indicadas à parte no relatório.
- Uma peça oca importada pode ser preenchida com uma treliça: o Solidon determina o espaço interior através do respiro e diz que o determinou assim.
- Reduzir triângulos já não rasga modelos fechados. Onde a forma não permite outra coisa, o relatório indica em quantas partes o modelo se dividiu.
- Reduzir triângulos alcança agora o seu objetivo também em casquilhos, anéis e caixas com aberturas.
- Um conjunto STEP importado chega como corpos separados, cada um com o seu nome e cores de face, em vez de um todo fundido.
- Antes de incorporar um conjunto STEP, escolhe quais os corpos de que precisa; uma peça espelhada continua a ser um reflexo.
- A exportação STEP escreve nomes e cores de face no ficheiro; uma peça relida mantém o seu nome inalterado.

### Utilização e sistema

- Cada ação confirma brevemente o seu resultado onde clicou, além da linha de estado.
- Um erro do programa deixa um registo local que é anexado ao relatório de apoio. Nada é enviado por si só.
- A configuração de «Modelo a partir de texto» descarrega por si própria o modelo de imagem em falta em vez de o remeter para uma pasta.
- O Solidon arranca em metade do tempo.
- Com uma característica selecionada a dica mantém-se, e uma indicação sobre a pega já não apaga a última confirmação.
- Se um passo do assistente parar a avaliação, a proposta retira-o por completo e mostra o estado anterior.
- Mover ou rodar um modelo com 200 000 triângulos responde em meio segundo em vez de oito.
- Anular responde de imediato em vez de após dois segundos e meio.
- Ao alterar o diâmetro do furo na placa perfurada, a primeira pré-visualização surgiu em 0,57 segundos durante a medição, e cada seguinte em 0,13 segundos.
- O esvaziamento foi entre 7 e 25 por cento mais rápido nos três modelos medidos.
- Uma entrada de menu e um aviso discreto na vista levam ao apoio voluntário ao Solidon via PayPal ou GoFundMe.
- O cartão do questionário mostra agora as cores certas também no tema claro.

- A aplicação Windows e o instalador têm assinatura digital. A assinatura confirma a identidade do editor e permite detetar alterações posteriores.

## 0.4.4

### Editar

- O ângulo de saída alcança agora todas as faces verticais, mesmo as estreitas, e funciona em modelos importados.
- A fusão suave deixa faces laterais lisas em vez de arestas desfiadas.

### Selecionar e utilizar

- Uma bobina no inventário de filamentos pode ter até quatro cores. Bambu Studio, OrcaSlicer e ElegooSlicer recebem todas as cores, os outros slicers a primeira.
- Uma aresta selecionada mostra apenas as ações que atuam numa aresta.
- Sem seleção, o caminho para os blocos continua visível.
- O campo de pesquisa só aparece onde há algo para encontrar.
- Uma divisória do organizador leva ao seu editor de compartimentos em vez das ações da sua face.
- A janela para colocar um furo indica que o ponto se escolhe na vista.
- Na janela «Gerar modelo», o campo de descrição mantém a sua altura mesmo quando aparece o aviso sobre o programa adicional em falta.

### Mover e verificar

- As sugestões de impressão chegam muito mais depressa: uma figura com 2,3 milhões de triângulos em segundos em vez de minutos, e abrir a janela de impressão uma segunda vez não volta a medir.
- Uma bobina importada de outro tipo de material que nenhuma peça usava fechava o slicer sem uma palavra. Agora cada bobina de uma placa recebe um perfil completo.
- Se o slicer não tiver um perfil do fabricante para o seu tipo de material, a janela de impressão di-lo e usa os valores do Solidon, não um perfil de outro material.
- Dois corpos podem ser empurrados um contra o outro para os unir ou fundir suavemente. Só é trazido de volta o que fica fora da área de impressão.
- Se um ajuste aponta para uma característica que já não existe, um botão leva ao histórico.
- Orientar para impressão e Dispor na mesa colocam peças de filamentos diferentes em placas próprias, para que um bico não purgue sem parar. Vários bicos indicam-se na janela de impressão.

### Inventário de filamentos

- Uma anulação no histórico de movimentos pode ser revertida de novo, com o mesmo botão.
- Alterar apenas o nome ou o local de uma bobina já não conta como nova contagem; os seus registos continuam anuláveis.
- Após uma anulação, «Registar sem perguntar» regista mesmo uma nova impressão em vez de dizer apenas «registado».
- As datas de compra e abertura têm um calendário na sua língua. Uma bobina recusada volta à janela em vez de desaparecer.
- A importação do slicer cria uma bobina nova se o nome for igual e a cor diferente, em vez de recolorir a sua.
- Se o ficheiro do inventário não se conseguir ler, um botão recupera o último estado: o Solidon guarda-o sozinho a cada gravação.
- A página de detalhe mostra resto, data de compra e preço; o código de oito caracteres só aparece se duas bobinas tiverem o mesmo nome.

## 0.4.3

### Reconhecimento e edição

- Furos cegos pouco profundos, pequenas faces funcionais e roscas curtas são reconhecidos melhor. Os fundos dos alojamentos para ímanes pertencem aos respetivos furos.
- Altere os furos com os seus escareados e entradas, mantendo as medidas previstas. O fundo continua associado mesmo após grandes alterações do diâmetro.
- Reconheça elementos num ponto escolhido de uma malha grande e edite-os de imediato. O reconhecimento e a alteração podem ser desfeitos em conjunto.
- A seleção e a pré-visualização mostram o corpo completo. Contornos e etiquetas identificam a zona escolhida; as letras inalteradas ficam sem manchas laranja.
- As arestas podem ser selecionadas em qualquer corpo e arredondadas ou chanfradas, também em modelos importados.
- Os furos, cilindros e arredondamentos nascem dos mesmos pontos no Windows, macOS e Linux. Um projeto é reconhecido e editado da mesma forma em qualquer computador.

### Construção

- Os organizadores permitem medidas ligadas, divisórias editáveis individualmente e células repetidas. Tabuleiro, rebordo, fundo e pé ampliam a biblioteca.
- Os campos de furos, furos oblongos e hexágonos seguem uma região desenhada. Respeitam áreas reservadas, margens e pontes mínimas.
- As abraçadeiras de perfil incluem duas carcaças e dois insertos ajustados. Admitem perfis redondos, ovais ou desenhados; os insertos podem ser substituídos depois.
- Um desenho fechado ou uma abertura escolhida cria uma ranhura e uma junta separada. Pode ajustar materiais, secção e saliência; as paredes restantes são verificadas.
- Os padrões de superfície chegam ao limite da face e deixam os furos livres. Os padrões existentes podem ser editados diretamente no painel de seleção.
- Cortar fora mantém um lado de um plano e fecha a face de corte — para paredes traseiras lisas e paredes à mesma altura. Os boleados junto a paredes ligeiramente inclinadas voltam a poder editar-se.

### Importação e utilização

- Escolha visualmente os contornos SVG e DXF antes de criar o corpo. Os ficheiros GLB e GLTF mantêm as dimensões e a orientação corretas.
- As medidas do projeto continuam ativas nos esboços das peças e nas pré-visualizações de colocação. O enquadramento inclui todas as placas de impressão visíveis.
- Pode remover filamentos da estante. Os primeiros passos começam pelo slicer; os comentários abrem rapidamente e preparam os anexos em segundo plano.
- Delete numa face remove o corpo e diz-o; Ctrl+Z traz o corpo de volta. Numa vista rasante, um corpo arrastado segue o ponteiro, e a face escolhida mantém-se no primeiro clique do esboço.
- O chat local recebe uma janela maior e já não encurta o seu pedido.
- O diâmetro do bico define-se na impressora. A transferência escolhe então a máquina correta no slicer, mesmo que aí esteja selecionado outro bico.
- A reparação fecha os modelos que se tocam ao longo de uma aresta em vez de os abrir ainda mais.

## 0.4.2

### Desenho

- Dois cliques criam um polígono regular: primeiro o centro, depois um canto. O número de cantos define-se antes — de três a doze. Um diâmetro escrito fica como cota.
- Um furo oblongo nasce de dois cliques nos centros das suas extremidades arredondadas; a largura fica ao lado na barra. Ambas mantêm o tamanho e os flancos, direitos.
- Quatro novas condições: ângulo em graus entre duas linhas, igual comprimento ou tamanho, ponto a meio de uma linha, concêntrico para dois círculos ou arcos.
- Um ponto arrastado fica no ponteiro e os vizinhos seguem-no: um canto do retângulo leva os dois lados consigo, uma linha estica a forma. Antes, o canto só ia parte do caminho.
- Um retângulo feito com cliques é livre: sem ponto fixo, sem cotas enquanto não as escrever. Uma largura ou altura escrita fica como cota — como no Fusion.
- As formas do menu podem ser deslocadas; as cotas da entrada do menu mantêm-se. Para alterar uma cota na vista, faça duplo clique no seu cartão.
- Arredondar e chanfro no editor de esboços: apontar para um canto, escrever o raio ou a cota, clicar. O arredondamento fica no seu canto ao arrastar; o chanfro cria uma aresta inclinada.
- Se uma restrição segura um ponto, a linha diz qual — e que um clique direito no ponto a retira. Antes, o ponto ficava parado sem explicação.
- Fixo quer dizer fixo: um ponto fixado já não segue o arrasto. As linhas exatamente horizontais ou verticais mantêm-se assim, mesmo que depois arraste um canto.

### Construir e alterar

- Rodar um furo oblongo roda-o, em vez de cortar um segundo atravessado. E alterar um furo oblongo que o próprio utilizador puxou altera esse passo; o histórico não recebe um segundo.
- Um STL que exporte após «Alterar furo», «Mover elemento» ou «Aplicar um chanfro» num modelo importado chega fechado ao slicer. Antes, a junção abria quando o slicer a soldava.
- Se no chat indicar só um eixo — «furo em x = 20» —, o furo desloca-se apenas aí. Antes saltava para zero nos outros dois eixos.
- Arredondar avisa à partida que um corpo exato admite um raio menor do que uma malha, e o que ajuda então: um raio menor ou continuar na malha.
- Abrir o mesmo ficheiro duas vezes dá dois nomes distinguíveis: «suporte» e «suporte 2». Antes ambos os corpos tinham o mesmo nome, na árvore e no relatório.
- As mensagens que remetem para os valores à direita nomeiam a janela como ela se chama: Seleção. Antes diziam «painel de características».
- O passo «Reduzir triângulos» avisa quando uma peça já tem menos triângulos do que o número indicado: então não há nada a reduzir. Antes ficava como estava, sem uma palavra.
- O passo «Dar uma pose» sem esqueleto avisa que os ossos nascem no editor de esqueleto — dois cliques por osso. Antes o passo não movia nada, em silêncio.
- Um furo que desloque, rode, duplique ou altere avisa quando com isso ultrapassa o bordo da peça — como ao furar. Antes só se via o resultado na imagem.
- Deslocar e duplicar um furo com escareado deixam o volume da peça inalterado. Antes faltava depois até um milímetro cúbico.
- Se um passo parte uma peça em pedaços soltos, o relatório diz-o — com o caminho de volta por Ctrl+Z.

### Reconhecimento

- Uma parede curva — a ponta de uma patilha, o fundo de uma ranhura — chama-se agora assim. Antes dizia «Arredondamento» com uma aresta que não existe. O raio pode ser alterado.
- Um furo com saliências na parede, como o anel de um fecho de baioneta, é um furo. Antes aparecia como um furo oblongo tão comprido quanto largo, e qualquer ação removia as saliências.
- Uma ranhura com chanfro no bordo é uma ranhura; o chanfro faz parte dela. Antes, uma moldura mostrava 126 escareados avulsos na árvore.
- Um entalhe ou a ponta redonda de uma lingueta já não é um furo, e dois pedaços da mesma parede redonda aparecem como um só na árvore.
- Um pedaço de cone sem bordo próprio chama-se face cónica. Pode ver-se, mas não editar-se isoladamente — e cada linha o diz.
- A parede interior de uma roda com raios não é um furo, e um copo com um buraco no fundo não é uma passagem. Antes, «Deslocar» cortava ali os raios.
- Os modelos grandes são reconhecidos até trinta vezes mais depressa: uma peça de relojoaria com 500 arcos demorava dois minutos, agora quatro segundos.

### Vista e utilização

- Uma caixa de seleção num diálogo passa agora a alternar em toda a linha — também ao clicar no seu texto. Antes só a pequena caixa respondia, e «Abrir em cima» ao escavar parecia não reagir.
- Quando uma pré-visualização não consegue mostrar nada, a vista diz porquê — por exemplo «Este plano não divide o objeto». Se o volume não muda, a faixa di-lo; se o cálculo demora, também.
- O passo «Dividir» começa no meio da peça em vez de na sua face inferior. O número continua editável.
- Uma ferramenta que nada pode fazer nesta peça aparece a cinzento e diz porquê — «Fechar superfície aberta» numa peça fechada, «Separar em peças» numa só, «Treliça» sem cavidade.
- Atribuir um filamento já mostra a cor na pré-visualização; igualar e subdividir triângulos mostram a nova malha com as suas arestas. A barra de espaço traz o antes.
- Escavar uma peça com furos na casca diz agora que a casca é o problema e oferece «Reparar e tentar de novo» — em vez de avisar que nenhum cálculo funcionou.
- No elemento escolhido aparece a cinzento o que ali só poderia falhar — «Rodar elemento» num furo escareado, por exemplo — com o motivo. E a pré-visualização diz se ao aplicar virá uma pergunta.
- Um campo que nada faz com a forma base escolhida já não aparece a cinzento no diálogo — surge com a forma que precisa dele. Um retângulo mostra à frente quatro campos em vez de oito.
- Com o ecrã a 150 ou 200 por cento, o encaixe, as pegas e as marcas alcançam o mesmo que a 100 por cento. A pega fica em tamanho completo e um clique trémulo continua a ser um clique.
- Num modelo grande a pré-visualização chega em menos de um segundo em vez de vários: o Solidon calcula-a de forma mais grosseira e escreve «Pré-visualização aproximada». Aplicar continua exato.
- O passo «Separar por uma linha desenhada» começa no meio da peça e não na sua face inferior, como «Dividir». Antes a pré-visualização mostrava apenas que o plano não separa nada.
- O passo «Alinhar por uma característica» pede-lhe agora que escolha a segunda característica em vez de lhe explicar uma notação.
- O arranque já não espera pela placa gráfica: é procurada enquanto a janela é construída. Em máquinas que demoravam, o programa ficava parado durante segundos.
- O que não é possível numa característica aparece a cinzento com o motivo — a mesma frase que a operação teria dito depois do clique. As frases ficaram mais curtas.

### Ficheiros e exportação

- Um 3MF do slicer abre agora mesmo quando as cores não se leem sem ambiguidade: o modelo chega numa só cor e o relatório diz porquê. Antes, o ficheiro ficava fechado.
- As faces pintadas no Bambu Studio, Orca e Elegoo chegam exatamente como foram pintadas — mesmo onde uma cor atravessa um triângulo. Antes, isso contava como «ambíguo».
- Um relevo de texto do slicer Elegoo ou do Bambu Studio no ficheiro travava a importação. Agora o ficheiro abre.
- Modificadores e bloqueadores de suportes do slicer já não aparecem como corpos, e um recorte («peça negativa») é subtraído — como no slicer.

### Blocos e ajustes

- Um bloco para furos — inserto térmico, alojamento de porca, assento de rolamento, rosca, parafuso — assenta logo no furo escolhido, em vez de no centro da face.
- Ao arrastar um bloco pela pega na vista, move-se o bloco inteiro, mesmo agarrado por uma aresta do furo de fechadura. Antes só se deslocava essa característica.
- Ganchos e furos de um bloco aparecem à direita como quantidade, e não como «2,00 mm». E depois de «Alterar medidas» o bloco continua selecionado, mesmo com outras características.

## 0.4.1

### Construir e alterar

- Arredondar e chanfrar funcionam agora também num modelo importado: escolhe-se uma aresta na vista e indica-se o raio ou a largura. Antes só funcionavam num corpo próprio.
- Deslocar a face e o ângulo de saída funcionam igualmente num modelo importado, e aí também se pode alterar ou retirar um arredondamento reconhecido.
- Deslocar a face move a face em que se clicou. Numa escada os restantes degraus ficam onde estão, em vez de se moverem todos ao mesmo tempo.
- O círculo de furos e a grelha de furos são formas próprias no desenho, com as suas medidas: número, círculo primitivo e diâmetro. Antes eram seis círculos à mão.
- Novidade: «Adicionar cordão», uma tira redonda ao longo das arestas escolhidas — por fora como cordão, num canto interior como cordão de canto. Um corpo exato passa assim a malha; Desfazer recupera-o.
- Uma aresta escolhe-se agora na vista: primeiro clique o corpo, depois a aresta. O comprimento e os botões Arredondar e Chanfro ficam à direita. Antes era preciso reconhecê-la numa lista.
- Num tubo, o bordo interior e o exterior arredondam-se ou chanfram-se em separado. Antes chamavam-se os dois da mesma forma, e a edição atingia um dos dois.
- O ângulo de saída deixa a área de apoio intacta, mesmo que a peça não esteja à altura zero. Antes, uma peça elevada era também afunilada em baixo.
- Varrer ao longo de um percurso começa com a secção certa e mantém as aberturas no contorno — um anel continua a ser um tubo, em vez de começar deformado e ficar maciço por dentro.
- Um par de contrapeças inserido conta como alteração: é gravado com o projeto e perguntado ao fechar. Antes podia perder-se em silêncio.
- O cadeado ao lado de uma medida fixada no editor de esboços é agora um símbolo desenhado com explicação. Nalguns computadores aparecia ali um quadradinho.

### Furar e posicionar

- Ao colocar um furo, uma caixa transforma-o num furo oblongo: indica o comprimento e a direção, e a pré-visualização mostra ambos.
- Um furo que já está no modelo pode ser esticado depois até formar um furo oblongo — o diâmetro mantém-se como foi medido.
- O furo oblongo é alargado pela tolerância do material em todo o seu comprimento. O curso que um parafuso tem lá dentro continua a ser o que indicou.
- Se um furo oblongo ultrapassar a aresta numa das pontas, o Solidon avisa, mesmo quando o seu centro está bem dentro do material.
- Um furo oblongo consta na árvore de objetos como furo oblongo, com a sua largura e o seu comprimento — também num modelo que abriu e que outra pessoa desenhou.
- Um furo oblongo existente pode ser esticado depois, e a sua direção mantém-se onde estava.
- Um furo ou um furo oblongo selecionado ajusta-se diretamente na vista com «Ajustar na vista»: uma pega para deslocar e rodar, botões para esticar, cotas a arestas e centros.
- Só «Aplicar», à direita, faz disso um passo; Escape descarta. Um furo oblongo esticado mostra o seu comprimento e mantém a sua forma quando o desloca pela pega.
- Um campo de coordenada vazio significa agora «deixa o furo onde está». Assim pode colocar-se um no centro da peça, o único sítio que antes não alcançava.
- Um furo desloca-se com «Alterar furo» agora também no corpo exato — e na malha move-se mesmo. Se sair para lá da aresta, o Solidon diz que já não é um furo.
- A largura de um furo oblongo altera-se com «Alterar furo». O curso que um parafuso tem lá dentro mantém-se.
- Se um furo ou um furo oblongo atravessar a peça por completo, de modo que ela se desfaz em pedaços, o relatório di-lo — em vez de dizer apenas que o furo ultrapassa a aresta.

### Reconhecimento

- Um escareado sobre um furo passa a manter-se também numa peça com superfícies redondas e curvas — antes perdia-se aí, e o furo e o seu escareado já não podiam ser deslocados em conjunto.
- Uma cavidade inteiramente dentro do material, sem saída, aparece na árvore de objetos como bolsa de ar, com o seu volume. Antes aparecia como um furo que não existia.
- Num modelo muito curvo, o Solidon diz agora o que foi medido em vez de lhe chamar uma digitalização, e que formas ficam de fora numa superfície dessas.
- O reconhecimento de características em modelos grandes de forma orgânica é cerca de um quarto mais rápido. Encontra o mesmo que antes.
- Se entre um furo e a parede à sua volta ficar menos material do que o seu aguenta, o relatório di-lo, medido na peça acabada.
- O mapa de defeitos de malha marca agora também as faces que se atravessam. Antes via apenas arestas abertas e ramificadas e dava um modelo desses por são.
- A análise por camadas de uma peça com serrilha fina demora agora metade do tempo; os pontos indicados são os mesmos.
- Se uma ponte conta como demasiado longa depende agora do seu bico: duas linhas de um bico de 0,4 são 0,84 mm, não um milímetro redondo. Alterações mais pequenas o chat já não anuncia como «+0,00 cm³».
- O reconhecimento de roscas precisa apenas de uma fração da memória e pode ser cancelado.
- Se um corpo não puder ser separado por causa de uma malha aberta, a reparação fica como botão no achado.
- Se um corte não puder ser tapado, o Solidon diz que o modelo não está fechado — e como continuar — em vez de apontar para o corte.

### Rotular

- Uma inscrição pode usar agora oito tipos de letra em vez de três, mais negrito e itálico. O negrito tem traços mais grossos com a mesma altura e continua legível onde o estilo normal borra.
- Ao lado dos tipos de letra direitos há agora um redondo e um manuscrito, ambos num só estilo. Os oito viajam com o programa, por isso um projeto fica igual em todo o lado.
- Se um tipo de letra for demasiado fino para o seu bico, o Solidon diz a partir de que altura aguenta, em vez de o imprimir e deixar as letras empastarem.
- Os lados curvos de uma letra — o arco do D, o contorno do o — aparecem agora na árvore de objetos como os retos e aceitam um filamento próprio. Antes faltavam por completo.

### Blocos e ajustes

- Um bloco do catálogo aparece logo na vista: na face selecionada ou em cima do corpo, com cotas e pega. Um clique coloca-o noutro sítio, «Aplicar» insere-o.
- Se separar em peças distintas um corpo com um ajuste, o Solidon pergunta a que peça se refere agora o ajuste — em vez de o mandar desfazer os passos.
- O casquilho de inserção M2,5 recebe o seu furo de montagem segundo a ficha técnica: 4,0 mm em vez de 3,6. Um projeto mais antigo com este casquilho avisa ao abrir que a medida mudou.
- O aviso de um braço de encaixe que parte conta com a direção de impressão desfavorável: um braço que flete atravessado às camadas aguenta menos, e isso está agora na frase.
- O gerador de variantes grava em cada peça o seu valor na face superior. Se uma peça for demasiado pequena para um número legível, o relatório di-lo e indica a ordem na mesa.

### Vista e utilização

- As ações para um corpo ou característica selecionados estão à direita, em grupos que se fecham, com pesquisa. Os menus Objeto, Modificar e Preparar desapareceram; os atalhos continuam.
- O clique direito num corpo ou numa face mostra apenas o que só existe aí: o passo por trás, o esboço na face, o ocultar. O botão «Blocos» está em cor de destaque.
- Se a cadeia para num passo, as ações ficam bloqueadas e dizem porquê; tentar mostra logo as saídas do relatório. Antes, o passo ficava em silêncio atrás da paragem, nunca calculado.
- O seletor de mesas no cabeçalho fica ao lado do nome da impressora, já não por cima — mesmo quando as mesas só chegam com o projeto aberto.
- O relatório agrupa mensagens iguais numa linha, com o número entre parênteses à frente. Um clique seleciona todas as peças afetadas; uma ação pergunta a quais se aplica.
- A coluna direita com relatório, chat e tour ficou um pouco mais estreita; o espaço vai para o modelo.
- Ao medir, a vista passa a projeção direita e volta depois. Em perspetiva aponta-se ao lado, tanto mais quanto o traço estiver longe do centro da imagem.
- Quem apenas olha para um modelo já não recebe a pergunta sobre gravar ao fechar. Em troca, os ficheiros importados aparecem em «Abertos recentemente».
- Se empurrar um corpo para além do bordo da mesa com a pega, o Solidon volta a colocá-lo num sítio livre. Um valor escrito é executado tal como foi introduzido.
- A escolha do idioma nas definições faz efeito de imediato; as restantes entradas mantêm-se e Cancelar repõe o idioma. Vale também na configuração inicial, que uma mudança já não termina.
- Ao fim de um quarto de hora de trabalho, o Solidon pergunta uma vez por versão pelo seu comentário. Responder ou fechar: nesta versão a pergunta não volta.
- Se o rato 3D estiver bloqueado, o Solidon indica o caminho para o libertar em vez de o ignorar em silêncio.
- O caminho para a impressora chama-se no menu «Preparar a impressão …» em vez de «Definições de impressão …». A janela por trás é a mesma.
- A tecla Enter num campo de medida à direita aplica o passo, e a tecla Tab percorre os campos de cima para baixo.
- A paleta de comandos pré-seleciona a melhor correspondência, não a primeira executável. «Arred» e Enter criavam antes um paralelepípedo.
- Se arrastar um corpo com o rato, ele fica no ponteiro mesmo sobre o fundo vazio, em vez de parar e saltar assim que volta a haver algo por baixo.
- Também depois de abrir um projeto, o primeiro clique no modelo já não engasga; a preparação corre assim que os corpos estão no lugar.
- Os movimentos finos da roda — touchpad, rato de alta resolução — fazem agora zoom em vez de se perderem.
- Voar com a tecla Ctrl premida termina assim que a solta. Antes a vista continuava a voar.
- Com uma escala de ecrã elevada acerta nas pegas com a mesma facilidade que a 100 %.
- Depois de uma mudança de achado, os botões do relatório apareciam por instantes como pequenas janelas próprias. Isso acabou.
- O contorno de camada de uma peça na segunda mesa fica sobre essa peça, não ao lado da primeira.
- No ecrã inicial ficam apenas os menus que aí fazem alguma coisa.
- Um segundo bloco do mesmo tipo — uma segunda tampa de rosca, por exemplo — recebe um número em vez de se chamar como o primeiro.

### Ficheiros e exportação

- Antes de escrever, a exportação mostra o que o relatório encontrou: uma parede fina, um ajuste violado. É você que decide se o ficheiro é escrito à mesma.
- O Solidon guarda pasta, formato e esquema de nomes por projeto. Se surgirem vários ficheiros, o padrão do nome fica no campo e pode ser alterado.
- Ao ler um modelo, o progresso mantém-se até o modelo estar mesmo lá, e a indicação diz «A ler o modelo» em vez de «A carregar o projeto». Cancelar fica acessível todo esse tempo.
- Uma pergunta respondida sobre que característica um passo quer dizer continua respondida — mesmo depois de fechar e voltar a abrir o projeto.
- Se o ficheiro ligado de um projeto não estiver acessível, o projeto grava-se e abre-se na mesma; o relatório nomeia a origem. Se faltarem permissões, o Solidon di-lo em vez de o dar por danificado.

### Mesa de impressão e entrega

- Se um corpo feito de peças soltas — um letreiro, por exemplo — não cabe inteiro em nenhuma mesa, o relatório propõe separá-lo e orientá-lo logo: um clique e as peças ficam nas mesas.
- Abrir no slicer entrega ao ElegooSlicer, Orca e Bambu Studio todas as mesas num único ficheiro — uma janela em vez de uma por mesa.
- Na separação, no letreiro e na textura o relatório indica o número na frase, onde antes estava um marcador entre chavetas.
- Um letreiro ao qual atribuiu um filamento mantém-no ao ser separado em letras. Antes chegava ao slicer num segundo filamento cinzento, com o atribuído ao lado sem uso.
- Com várias mesas, as peças chegam agora ao slicer onde ele tem as suas mesas: na grelha que ele próprio dispõe. Antes, as letras da terceira e quarta mesa ficavam ao lado de tudo.
- Se ao fatiar ficar uma bobina por usar, o Solidon di-lo com o nome dela. Antes o slicer indicava êxito e na impressão faltava um filamento.
- Se um slicer se fechar de repente, o Solidon di-lo assim. Antes dizia-se que não tinha escrito nenhum ficheiro de impressão.
- O Creality Print é reconhecido como slicer e pode ser escolhido na janela de impressão, com as suas impressoras, processos e filamentos.
- A janela de impressão abre logo com o slicer escolhido da última vez; a procura de outros corre em segundo plano. Antes, o clique em Imprimir podia não mostrar nada durante dez segundos.
- A escolha do slicer mostra todos os programas instalados — também um segundo Flatpak ou um segundo AppImage. Antes faltava o segundo de cada local.
- Um filamento de um pacote de fabricante do PrusaSlicer chega à entrega com os seus próprios valores, não com os do primeiro filamento do ficheiro.
- Na entrega como STL — ao Cura, por exemplo — o Solidon diz que as definições por peça não viajam, e indica a proposta para a mesa inteira, em vez de afirmar que estão aplicadas.

### Filamentos e armazém

- O armazém de filamentos também pode ser gravado numa pen FAT32, num disco exFAT ou numa partilha de rede. Antes, aí falhava cada gravação.
- Se o armazém não puder ser lido, o Solidon di-lo também no seletor de filamento, com o botão «Tentar de novo» — em vez de uma lista vazia.
- O consumo medido no ficheiro de impressão conta também o material extrudido sem percurso e não conta as retrações duas vezes. Se o slicer escrever a quantidade, vale o número dele.
- Quem ao descontar o consumo escolhe «Não registar» não volta a ser perguntado por essa saída; ela fica acessível em «Não registado».
- Se criar uma bobina nova ao descontar o consumo, as bobinas escolhidas, as quantidades introduzidas e as repartições mantêm-se.
- A árvore de objetos mostra no corpo e na face apenas os filamentos que lá estão mesmo — uma face com filamento próprio leva o seu, não a lista do corpo inteiro.
- Cancelar durante a procura de perfis de filamento faz efeito de imediato.

### Chat e IA

- Antes do primeiro pedido a um gerador de modelos, o Solidon diz que dados vão para lá.
- Se outro processo ocupar a placa gráfica, o chat espera de forma visível em vez de ficar parado.

### Atualização, instalação e sistema

- Os pacotes para Mac estão assinados e notarizados. O desvio por «Privacidade e Segurança» → «Abrir mesmo assim» deixa de ser preciso.
- Em «Apoiar o Solidon» pode agora escolher-se GoFundMe ao lado do PayPal; só o seu clique abre o navegador, e sem navegador pode copiar-se o endereço.
- Se o seu código de compra estiver numa unidade cujas permissões de ficheiro não se conseguem definir — FAT, partilha de rede —, continua legível. Antes, aí contava como inexistente.

## 0.4.0

### Construir e alterar

- As contrapeças, como um pino e o seu furo, assentam nas duas peças num único passo. As medidas comuns indicam-se uma vez e um só desfazer retira o par.
- Unir dois contornos aceita agora dois desenhos próprios: redondo em baixo, angular em cima. É assim que nasce o adaptador de um tubo para uma calha.
- Varrer ao longo de um percurso segue um traçado desenhado com vários cantos e arcos, e não apenas um arco uniforme. Nos cantos vivos, o Solidon corta em meia-esquadria.
- A concordância e o chanfro atuam também numa única aresta. Escolhe-a numa lista que indica cada aresta com a sua posição e o seu comprimento.
- Um bloco chega a vários sítios num só passo: quatro furos recebem juntos os seus casquilhos e um só desfazer retira os quatro.
- Novidade: *Verificar o percurso de encaixe* leva uma peça à sua posição final e indica onde embate pelo caminho, mesmo quando as duas encaixam no fim.
- Cada bloco pode ser escrito como código OpenSCAD, a partir do catálogo ou da linha de comandos.
- O núcleo exato fura também numa face inclinada, com escareado e alargamento; os padrões e as montagens de encaixe mantêm-se.

### Furar e colocar

- Ao colocar um furo, a pré-visualização mostra o contorno da boca em vez de um cilindro semitransparente. O ponto que interessa fica desimpedido.
- A pré-visualização acompanha o rato com fluidez: a procura da face sob o ponteiro já não recomeça a cada movimento.
- Os campos de medida afastam-se do ponto onde nasce o furo, em vez de ficarem por cima dele.
- Quem escolhe uma operação que se coloca no modelo começa logo a colocar; o botão anterior desaparece.
- Depois de confirmar as medidas, a profundidade regula-se com o rato. O modelo fica translúcido e a vista roda de lado para que possa olhar para dentro do furo.
- Ao arrastar, a profundidade encaixa por instantes nos pontos com significado: o meio do material e a sua face posterior.
- O paralelepípedo, a esfera e os restantes corpos base movem-se e rodam já na pré-visualização, com a mesma pega de um corpo terminado.
- Os corpos base ganharam um ângulo de rotação: a direção diz para onde aponta o corpo, o ângulo diz como fica virado em torno dela.
- Furar num cilindro, numa esfera ou num toro deixou de produzir em cada furo o aviso de que ultrapassa a borda.
- Um furo com escareado é removido por inteiro após confirmação, em vez de deixar o escareado sem volta atrás.

### Características e seleção

- Um furo em que clica passa a oferecer apenas as ações que ali fazem alguma coisa; antes apareciam também o letreiro e a atribuição de filamento.
- Cada ação sobre uma característica aparece uma vez e não duas, e desaparece o cabeçalho de bloco por cima de uma única linha.
- Num escareado existente, *Escarear* volta a estar acessível.
- Na árvore de objetos, as características do mesmo tipo só se agrupam se a medida também coincidir. Dez concordâncias de raios diferentes voltam a figurar em separado.
- Um corpo com filamento atribuído volta a mostrar a sua seleção na imagem, em vez de ficar cinzento como os restantes.
- Os campos de uma característica levam o seu nome: um leitor de ecrã diz a que pertence cada campo, em vez de repetir seis vezes caixa numérica, 0,00.

### Blocos e ajustes

- Os seus próprios blocos abrem-se de novo a partir do catálogo para serem editados, mesmo que o projeto de onde vieram já não exista.
- A escala de tolerâncias adota a medida real do furo em que a abre, em vez de um valor fixo de 6 mm.
- Os ganchos e as linguetas elásticas calculam com o material e o curso da mola, e não com uma regra prática. O Solidon assinala um braço que parte ao primeiro encaixe.
- Os três corpos de calibração nascem sem corpo auxiliar, e a escala de tolerâncias imprime-se como duas réguas numeradas que encaixam uma na outra.
- O aviso da mola mede o braço real, a dobradiça de película mexe-se, e o prende-cabos chega até à pré-visualização e à saída.
- Um bloco deposita material de apoio antes de cortar onde é preciso; e a sua pré-visualização assenta bem mesmo sem suporte.
- Um bloco explica que combinação de medidas não consegue construir, em vez de as cortar em silêncio.

### Filamentos e armazém

- O seu stock de filamento tem lugar próprio: um mosaico na página inicial e uma estante em vez de uma lista, com o nível desenhado como enrolamento no carrinho.
- Duas bobinas com o mesmo nome mantêm-se distintas. Cada uma leva o seu próprio resto, e a começada é a que interessa.
- Ao fatiar e ao entregar, o Solidon pergunta se deve descontar o consumo. Depois de fatiar é a quantidade medida no ficheiro de impressão, caso contrário uma estimativa.
- Cada lançamento é reversível, cada bobina leva o seu histórico, e só desconta sem perguntar quem o configura expressamente.
- Um filamento atribuído pode ser retirado outra vez sem que as faces vizinhas percam o seu.
- Uma face pintada chega ao Orca e ao PrusaSlicer com o seu filamento, e já não sem ele.
- Depois de retirado, o perfil do fabricante deixa de ir parar ao filamento errado.
- Na estante, a pesquisa e as ações principais ficam juntas, e o local de arrumação e a carga nominal constam da janela da bobina.

### Impressão e preparação

- O Solidon encontra o que o Cura tem: impressoras, perfis de processo e filamentos que antes ficavam invisíveis.
- Do PrusaSlicer, o Solidon retoma os filamentos carregados e a impressora definida por último.
- Se o seu slicer não conhece sequer a impressora, o Solidon di-lo, em vez de o mandar para uma lista onde não está nada.
- Mudar o nível de qualidade demora segundos e não quase um minuto, e a janela mantém-se utilizável entretanto.
- O aconselhamento sobre as definições de impressão olha para todos os corpos da placa e não só para a seleção. O que um corpo precisa mantém-se, mesmo que o vizinho dispense.
- Calcula em segundo plano, nomeia o corpo, mostra o seu avanço e pode ser cancelado.
- Uma ponte longa é avaliada pelos seus apoios reais, e o ângulo de saliência vale para a impressora, o bico, a altura de camada e a largura de linha com que foi medido.
- A velocidade excessiva é limitada no tipo de percurso afetado, em vez de aquecer cada vez mais o bico e a base.
- As propostas desmarcadas continuam desmarcadas, e uma mudança de filamento, cena, placa ou qualidade invalida de imediato um resultado ultrapassado.
- O afastamento ao dispor conta a borda de aderência e a estrutura de suporte: entre dois vizinhos ambas contam a dobrar.
- As peças são dispostas no meio da base, como fazem os slicers ao lado, e não no canto traseiro esquerdo.
- Orientar para impressão volta a dispor depois as peças rodadas. Um corpo que se deita ocupa mais superfície e antes acabava dentro do vizinho.
- Nas definições de impressão desapareceu a segunda escolha de filamento sob os perfis do slicer. Repetia o que o seletor de filamento já diz; obter os valores do perfil é agora um botão próprio.
- Orientar para impressão considera todos os corpos da cena, não só os marcados. Assim a mesa inteira desloca-se depois para o centro, em vez de uma peça rodada desviar de outra parada.

### Vista e utilização

- O ponteiro do rato do Solidon vale para toda a janela e para cada caixa de diálogo, e não apenas para a vista 3D.
- Mudar de variante numa caixa de diálogo de operação já não encerra a aplicação.
- Uma caixa de diálogo de operação aberta já não sobrevive em silêncio a uma mudança de projeto.
- As notas longas já não são cortadas enquanto ao lado sobra espaço livre.
- A partir da linha de comandos não era possível chamar *Atribuir filamento*; agora é.
- O primeiro clique e a primeira rotação já não engasgam: o que a vista tem de preparar para eles acontece agora no arranque.

### Atualização, instalação e sistema

- Em *Novidades* constam as três últimas versões. O histórico completo de todas as versões está em solidon3d.de e continua lá disponível.

### Manual e site

- As imagens de solidon3d.de mostram o modelo a toda a largura, e não como uma faixa entre os painéis.
- O manual e o site nomeiam todas as operações que existem, incluindo os novos editores de características.

## 0.3.5

### Vista

- A vista 3D desenha com uma nova camada gráfica. Dirige-se à placa gráfica através de Direct3D 12, Vulkan ou Metal e mantém-se fluida mesmo com vários milhões de triângulos.
- Reentrâncias e arestas destacam-se mais: a vista escurece os cantos, traça linhas de profundidade e acerta o ponto para onde aponta.
- As arestas dos corpos ficam como uma malha fina sobre a superfície, e as legendas mantêm-se quietas em vez de tremer ao rodar.
- Os nomes das características já não se sobrepõem e as suas marcas continuam visíveis também no corte.
- O indicador de eixos em baixo à esquerda enche o seu campo em qualquer direção de vista e as suas letras vêem-se por inteiro.
- As vistas fixas giram a câmara em torno do ponto para onde está a olhar. O seu enquadramento mantém-se em vez de voltar à cena inteira; para enquadrar continua a existir *Ajustar à vista*.
- Apontar através de uma abertura para a face que está atrás seleciona essa face e não o bordo da abertura.
- Os modelos grandes constroem-se mais depressa, porque arestas e normais são calculadas apenas uma vez por corpo.
- Se ao computador faltar o suporte gráfico de que a vista precisa, a aplicação indica os dois pacotes que têm de ser instalados.
- Se inclinar a vista perto de um eixo, ela encaixa aí e mantém a sua rotação, em vez de saltar para uma posição fixa.

### Ações para a seleção

- O relatório de verificação e o chat fecham à direita com a sua própria borda. As ações para a seleção ficam abaixo num cartão próprio, e entre os dois vê-se o modelo.
- Quais ações ficam à frente depende da seleção: com vários corpos Unir, Subtrair e Interseção; com um só Abrir furo, Esvaziar e Separar.
- Num furo selecionado aparecem Escarear e Fechar furo; numa face, Abrir furo, Cortar bolsa e Deslocar a face.
- Um corpo selecionado mostra ali os seus filamentos e permite alterá-los.
- Um campo de pesquisa no mesmo cartão encontra as restantes operações; características e peças ficam nas suas próprias áreas.
- A coluna da direita ficou mais larga: as ações para a seleção cabem por inteiro, em vez de se apertarem em metade da largura.

### Construir e alterar

- Unir, Subtrair e Cortar levam todos os corpos selecionados de uma vez, e não exatamente dois.
- Arredondar já não derruba a aplicação quando o raio é maior do que a parede que deve arredondar.
- Um corpo do núcleo exato continua exato se apenas o mover ou rodar. Arredondar e chanfrar continuam possíveis depois.
- A ferramenta de furação só sobressai à entrada do furo e recusa diâmetros que excedem a peça em várias vezes.
- Alinhar à face significa à face com um ângulo, e não com uma única distância entre pontos.
- Reduzir triângulos para numa resolução com nome, e o enchimento em treliça já não inventa um interior que não existe.
- O editor de esboços acerta arcos no círculo inteiro, encontra bordos de círculo, apaga com Del o elemento escolhido e não deixa Refazer pendente.
- A resposta durante a modelação já não declara sem efeito as alterações pequenas.
- Os interruptores de uma operação ativos por predefinição podem agora também ser desligados na linha de comandos.
- Um erro numa operação indica a sua causa: no registo, na linha que o parou e no relatório de erro.
- As entradas recusadas na colocação, no depósito de malhas e nas receitas chegam com uma proposta de ação em vez de um erro nu.
- As peças explicam que combinações de parâmetros não constroem, em vez de cortar medidas em silêncio.
- Um número inadequado de corpos selecionados é comunicado antes do cálculo, em vez de deixar uma entrada de fora sem se notar.
- Colocar sobre uma superfície só altera o documento ao confirmar; uma pré-visualização descartada não deixa nada para trás.
- As letras e os algarismos ficam no campo de entrada — as teclas de navegação só atuam quando não está a escrever ali.
- Separar em peças distintas transforma vários corpos soltos de um ficheiro num objeto cada um — o que não se toca não é uma só peça.

### Características

- Uma digitalização importada já não traz cúpulas nem taças inventadas; até agora surgiam às centenas de superfícies arredondadas suavemente.
- Várias roscas numa placa são nomeadas separadamente em vez de serem reunidas numa única característica.
- Esfera, toro e cone declaram a sua curvatura, os centros dos cilindros coincidem com os anéis das extremidades e os passos de rosca seguem o eixo.
- O painel de características só oferece ajustes quando há um segundo corpo selecionado e conhece cada grupo do núcleo.
- Os ajustes de corte automáticos já não atribuem duas vezes o mesmo nome.
- A deteção de características chega ao mesmo resultado mais depressa em malhas complexas.

### Impressão e preparação

- A busca de orientação julga em duas etapas: duzentas posições a partir das normais, nove delas na análise por camadas.
- A sua barra de progresso vai até ao fim, mesmo quando não havia nada a cortar.
- O slicer recebe o mundo da impressora e não o do Solidon, e um perfil próprio conserva a sua base do fabricante.
- Os perfis de laminação próprios ficam à frente do perfil do fabricante com o mesmo nome, e um AppImage encontra o seu inventário.
- A limpeza depois da importação conserva as atribuições de filamento.
- A impressora pertence ao projeto e muda-se tanto no cabeçalho como na janela de impressão; filamentos atribuídos, cores e os seus próprios valores de impressão mantêm-se.
- Cada corpo leva o seu filamento na árvore de objetos: um campo de cor antes do nome e um clique para atribuir outro.
- Várias bobinas do mesmo tipo de material continuam distinguíveis pelo nome e pela cor.
- As operações correspondentes têm o nome daquilo que fazem: *Atribuir filamento* e *Filamento numa face* em vez de *Colorir peça* e *Colorir face*.
- A entrega ao slicer resolve cada bobina segundo o seu próprio tipo de material; os seus próprios valores de impressão mantêm a prioridade.
- Se o mapa de suportes demorar demasiado, o cálculo termina com uma explicação e propõe reduzir os triângulos.
- A janela de impressão continua totalmente utilizável mesmo em janelas estreitas.
- Orientar para impressão alinha todos os corpos selecionados, não apenas o primeiro.

### Ficheiros e projetos

- Um 3MF com muitos níveis de duplicação é recusado antes que 432 bytes se tornem mil corpos.
- Um ficheiro de projeto pequeno já não pede gigabytes de memória.
- Um ficheiro GLB em milímetros chega em milímetros e não como metros.
- Uma gravação falhada já não leva consigo a última cópia de segurança, e cancelar cancela realmente a importação.
- Um erro tardio na leitura já não limpa a fonte do projeto seguinte.
- Se a pasta de cache não puder ser criada, o resultado já calculado mantém-se.
- Um conjunto de variantes incompleto já não é exportado em silêncio.
- O esboço descartado volta com Desfazer, e um segundo objeto do histórico já não deixa um Refazer desatualizado.
- Dois relatórios de erro do mesmo segundo já não se sobrepõem.
- As entradas escolhidas expressamente sobrevivem a guardar e voltar a abrir, em vez de serem substituídas por uma predefinição.
- Cancelar termina também o cálculo que ainda corre por trás de uma variante.

### Chat e IA

- Uma ferramenta adicional com um campo de tipo errado já não interrompe toda a série do agente.
- Para as variantes de esboço o agente indica apenas caminhos de menu que existem.
- Na geração de imagens os pesos chegam inteiros ou não chegam, e um único valor no campo de estrutura já não desencadeia uma geração não pedida.
- Um modelo local é medido também quando responde por HTTPS numa porta própria.
- O aviso sobre a participação da IA só vale com prova escrita, e uma mudança de idioma já não termina o comando à distância.
- A configuração do ComfyUI assume os pesos de modelo já completos, em vez de os descarregar de novo.

### Atualização, instalação e sistema

- A versão mínima é agora macOS 13, igual no pacote, no instalador e no site.
- Treze bibliotecas estão nas suas versões estáveis mais recentes, e o núcleo exato fala OpenCASCADE 8.
- Um pacote sem âncora de confiança no sistema traz o seu próprio conjunto, em qualquer plataforma.
- Uma transferência já não se interrompe depois de um tempo total fixo, e uma resposta a conta-gotas cumpre o prazo prometido.
- No Flatpak a aplicação encontra o gestor de pacotes do computador.
- No Linux e no macOS uma interrupção já não termina apenas no processo pai.
- A entrada de menu no Linux encontra o lançador mesmo sem entrada no caminho de procura.
- No Mac a janela de atualização diz que o Solidon volta por si depois do instalador.
- No Mac o rato 3D lê através do controlador do fabricante em vez de esperar ao lado dele.
- O ecrã inicial reconhece o sistema antes da primeira imagem, e a tabela de requisitos já não é cortada.
- Um anexo recusado já não conta como ausente para a resposta.
- O seletor de filamentos permanece na bobina certa depois de um cancelamento e mostra também a oitava.
- Um e-mail de apoio aberto à mão leva assunto e texto legíveis também dentro do Flatpak; um cancelamento deixa o relatório onde está.

### Manual e site

- O manual e as capturas mostram a interface renovada nas seis línguas.
- Os desenhos do manual mantêm o contraste do texto também nas suas notas laterais.
- A janela do manual carrega apenas as suas próprias figuras e nenhuma imagem alheia.
- O site diz num único lugar o que sai do seu computador.
- A introdução já não afirma que um furo está fechado quando Desfazer só repõe o diâmetro.

## 0.3.4

### Editar características detetadas

- Um furo e o seu escareamento associado passam agora a ser deslocados em conjunto, independentemente de qual dos dois é selecionado. O painel de características indica a ligação antes da alteração.
- Ao alterar um furo, o respetivo escareamento mantém-se associado por baixo dele na árvore de objetos e também pode ser ajustado diretamente.
- O painel de características agrupa ações indisponíveis iguais e indica claramente os grupos de campos afetados.

### Reconhecimento de características

- As roscas dos modelos importados são reconhecidas com maior fiabilidade; cones, pinos e esferas incorretos nelas deixam de aparecer como características separadas.
- As uniões estreitas entre formas reunidas deixam de criar numerosas características incorretas.
- O reconhecimento de características é visivelmente mais rápido em modelos grandes e detalhados.

### Mapas de análise

- Os mapas de análise estão disponíveis para mais modelos grandes.
- Se um mapa de análise for demasiado grande para um modelo, a mensagem oferece diretamente *Reduzir triângulos*.
- A análise da necessidade de suportes é consideravelmente mais rápida em modelos grandes.

## 0.3.3

### Exibição e seleção

- O primeiro clique seleciona a peça, o segundo o furo por baixo, e um clique ao lado cancela a seleção; o controlo escolhido mantém-se todo o tempo.
- Ao rodar, o horizonte permanece na horizontal: depois de um gesto a vista fica tão direita como antes, em cada um dos cinco controlos.
- O controlo e o tema escolhidos nas definições aparecem também assinalados no menu *Exibição*.
- Vários corpos selecionados continuam selecionados após um novo cálculo, e um arrasto move-os em conjunto.

### Trabalho no projeto

- Um projeto pode ser guardado mesmo quando uma característica traz um aviso.
- Alternar entre dois mapas de análise do mesmo corpo mostra de imediato o que já está calculado.
- Um projeto novo começa sem restos de uma pré-visualização que ficara aberta na altura da mudança.
- Através do controlo remoto, *Anular* retira exatamente o passo indicado e não o último.

## 0.3.2

### Editar características reconhecidas

- Ao deslocar, rodar ou remover um furo não fica material no local anterior, mesmo em peças com ranhura ou cavidade.
- O comando *Fechar furo* preenche agora exatamente o furo: o tampão já não entra numa ranhura nem engrossa a peça.
- Uma sede esférica é reconhecida como superfície esférica e não como escareamento, mesmo em modelos de malha fina, oferecendo as ações que lhe pertencem.
- Um furo duplicado recebe uma identidade própria e não a de um apagado antes, pelo que um ajuste continua a indicar a característica que designa.
- Também ao rodar, um furo passante avisa se na nova orientação já não atravessa.
- Uma característica recém-criada aparece no fim da árvore de objetos e não entre as anteriores.
### Visualização e seleção

- A pré-visualização desaparece assim que a alteração é aplicada; até agora o corpo de comparação com a faixa «ainda não aplicado» ficava sobre o furo terminado.
- A barra de espaços volta a alternar entre antes e depois apenas onde há uma pré-visualização, e já não em toda a aplicação.
- Um furo já não brilha na cor de seleção quando não há nada selecionado.
- O arco de rotação, a sombra, as marcas de arrasto e o anel do pincel desaparecem com a ação a que pertencem, também ao mudar de ferramenta ou fechar o projeto.
- Uma medida permanece na sua peça, mesmo que a vista mude para outra mesa de impressão ou para todas.
### Impressão e memória

- Se não couber tudo numa mesa, são criadas tantas mesas quantas forem necessárias; até agora o resto ficava ao lado da mesa, onde não é imprimível.
- A memória de características de modelos grandes mantém-se limitada; até agora podia ocupar até um gigabyte.
## 0.3.1

### Editar características reconhecidas

- As características reconhecidas podem ser movidas, rodadas, duplicadas e removidas: um furo, um pino ou uma cúpula; a cúpula sem rodar, por não ter orientação.
- Redimensionar funciona agora também num pino ou numa cúpula; até agora, apenas num furo.
- Os valores medidos já estão nos campos: acaba o desvio de tapar e voltar a furar com números copiados à mão.
- Um furo deslocado continua a ser o mesmo furo: cada ajuste que o indica mantém a sua referência.
- Quando uma ação não faz sentido para uma característica, continua visível e explica numa frase o motivo, em vez de faltar em silêncio.
- Um painel *Característica* abre-se à direita assim que se seleciona a primeira característica e mostra o que ali foi medido; pode ser desencaixado, fechado e retomado em *Vista*.
- Cada número é alterável: posição, diâmetro, profundidade e eixo definem-se no próprio campo, sem diálogo pelo meio.
- Um número alterado aparece como pré-visualização na imagem antes de ser aplicado.
- Uma caixa *Aplicar a todos do mesmo tipo* altera toda uma fila de furos de uma vez, com um único passo para anular.
- Duas características marcadas indicam a sua distância de centro a centro e por eixo.
- Um furo indica a sua medida normalizada — «mede 5,19 mm, o furo de passagem para M5» — e também avisa quando nenhuma serve.
- Um segundo furo igual ao primeiro obtém-se duplicando, em vez de escrever de novo as medidas.
- A tecla Del remove a característica selecionada e já não o corpo inteiro.
- Um duplo clique numa linha da lista de objetos abre o que a altera: o diálogo adequado numa característica reconhecida, o passo com as suas medidas numa criada.
- Um furo passante que após o deslocamento já não atravessa avisa, e um escareamento que fecharia o seu furo não pode ser deslocado.
- Reduzir um furo até deixar de o ser dá uma explicação em vez de pedir um relatório de erro.
- Numa face, um botão leva ao catálogo de blocos em vez de mostrar linhas que apenas dizem o que ali não é possível.
### Mover, rodar e selecionar

- A alça de movimento fica no que está selecionado: num furo, na sua abertura, e não no centro da peça.
- Move-se o que está selecionado: com um furo marcado, a alça e a barra deslocam o furo, não a peça inteira.
- Ao arrastar, uma pré-visualização transparente mostra para onde vai o furo e uma cópia pálida de onde veio.
- A sombra acompanha o movimento e mostra assim a altura acima da mesa.
- Ao rodar, um arco mostra quanto já rodou e que o ângulo encaixa em múltiplos de 45 graus.
- As rotações pequenas chegam: até agora um encaixe angular invisível engolia todo o movimento inferior ao seu passo.
- Numa face, a barra de movimento só oferece o que ali é possível e indica o motivo no botão, não numa mensagem após o clique.
- O botão *Aplicar* desaparece: aplica-se com Enter no campo ou arrastando a alça, e exatamente uma vez, não duas.
- Uma peça deslocada já não salta por um instante para a posição anterior ao largar.
- Um clique direito na lista de objetos acerta na linha indicada, e não nas duas acima.
### Vista e árvore de objetos

- A vista tem um comando próprio, e é a nova predefinição: arrastar com o esquerdo desloca, com o direito roda, a roda premida inclina e a roda amplia.
- Com W, A, S e D voa-se pela cena, e Q e E inclinam; o voo atravessa uma peça, enquanto a ampliação para à frente dela.
- Quem está habituado a outro comando escolhe-o nas definições: mantêm-se os esquemas para Cura, para Bambu Studio, Orca e PrusaSlicer, para um CAD e para Blender.
- A entrada *Ajustar à vista* enquadra a peça selecionada; sem seleção, toda a cena como antes.
- Uma peça sob a mesa de impressão fica visível: agora é a mesa que é transparente, não o modelo.
- Os corpos semitransparentes são desenhados na ordem de profundidade correta, qualquer que seja a ordem de criação.
- A vista definida mantém-se, em vez de voltar atrás no passo seguinte.
- A seleção e as mudanças na vista 3D ocorrem com transições suaves em vez de saltos bruscos.
- A partir de quatro características com o mesmo nome, a árvore de objetos mostra uma linha expansível com a sua quantidade em vez de centenas de linhas.
- Só é mostrado o que uma impressora consegue produzir: as características abaixo de meio milímetro desaparecem; num suporte de mangueira, 296 de 1130.
- Os arredondamentos com raio zero desaparecem assim da árvore de objetos.
- Um clique num corpo já não custa espera; num conjunto de 63 MB eram três quartos de segundo.
- Mudar a representação e reconstruir a imagem de modelos grandes leva um terço do tempo anterior.
### Desenho e introdução precisa

- O comprimento e a largura de um desenho selecionado são editáveis; o desenho segue o número alterado com as suas cotas.
- Uma cota mal colocada pode ser anulada isoladamente, e não apenas com todas as outras.
- Depois de extrudir um esboço, o diálogo volta a oferecer também o caminho para o subtrair.
- Uma cota escrita vale como foi escrita: 0,1 já não se torna 0,166667.
- O diálogo de unidades pede milímetros e mostra um número em vez de «nan».
- O campo do chanfro chama-se largura, e a mensagem correspondente também fala de largura e não de raio.
- Um clique na ranhura de um cursor coloca-o no ponto selecionado, e não uma página mais adiante.
- Ao medir, o ponto de destino fixa-se nas arestas do modelo e não em linhas que não existem na imagem.
### Abertura, gravação e ficheiros de troca

- O primeiro modelo de um projeto fica centrado na mesa de impressão em vez de onde o seu ficheiro o coloca; os restantes mantêm a sua posição.
- Um ficheiro danificado é recusado ao abrir, em vez de ser aceite e acabar no projeto ao gravar.
- A recusa indica o motivo — vazio, truncado, não é STL, não é 3MF, sem triângulos, com coordenadas inutilizáveis — e oferece *Escolher outro ficheiro*.
- A transferência interrompida de um ficheiro de modelo é reconhecida como tal.
- Os ficheiros com mais de oito megabytes são lidos com indicador de carregamento e progresso, em vez de deixar a janela catorze segundos sem resposta.
- Um nome de ficheiro chega ao disco tal como foi escrito, com espaços, acentos, parênteses e sinal de mais.
- Um modelo pode ser guardado como 3MF sem os valores de impressão do Solidon, para chegar inalterado ao slicer.
- Onde STEP não é possível para uma malha, a recusa oferece logo *Guardar como 3MF*.
- Um modelo com malha demasiado fina recebe *Reduzir triângulos* como botão no achado, e não apenas como conselho no texto.
- Um achado que afeta vários corpos pode ser resolvido para todos de uma vez, escolhendo quais, com um único Ctrl+Z para toda a ação.
- O comando *Auto Split* avisa quando um corte deixa uma superfície aberta, e um corte por um corpo editável já não deixa a cena vazia.
- Escalar uma peça abaixo do limite da máquina gera um achado; até agora só existia para demasiado grande.
- Os blocos próprios têm o mesmo aviso que os fornecidos.
### Impressão, slicer e filamento

- O diálogo de impressão mostra os perfis correspondentes à impressora definida, em vez de um acervo de 1001 entradas.
- Com uma Elegoo Centauri Carbon são quatro, e o correto vem pré-selecionado.
- Mudar a impressora no projeto arrasta volume de impressão, bico e código inicial: um projeto Prusa já não recebe a máquina da Elegoo.
- O slicer recebe os dados da máquina e devolve um ficheiro de impressão, em vez de abortar com «não compatível com a impressora».
- Se o slicer estiver noutra impressora que não a do projeto, o Solidon avisa em vez de o aceitar em silêncio.
- O aviso de perfil em falta indica a impressora em questão.
- A lista de filamentos fica vazia enquanto não for escolhido um perfil de máquina e indica esse motivo, em vez de oferecer 5962 bobinas.
- A seleção de filamento pode ser filtrada por fabricante, material e pelos valores que um perfil traz.
- Onde o Solidon coloca uma borda, indica qual a peça que dela precisa e por que motivo.
- O que a máquina não consegue fazer é indicado em todos os campos afetados, e não apenas num.
- As recomendações do relatório que o slicer não aceita já não prometem efeito.
- Os objetos de materiais diferentes vão para mesas separadas: a junta de TPU já não na mesa da caixa de PETG.
- O aviso de impressão dá um conselho em vez de remeter para números do contrato de licença.
### Mensagens, botões e informação

- Os botões bloqueados indicam agora no próprio botão o que lhes falta: com o rato, pelo teclado e para um leitor de ecrã.
- Entre eles *Fatiar* e *Abrir no slicer* sem slicer configurado, *Inserir* no catálogo de blocos e *Criar* no diálogo de modelo.
- As recusas não terminam apenas com a frase, mas com a saída.
- Um erro inesperado é explicado no idioma definido, em vez de recitar um texto interno em inglês.
- O diálogo Acerca indica quem está por trás do Solidon e quem responde ao feedback.
- Uma ligação para uma versão anterior leva à atual em vez de uma página de erro.
- A instalação em Windows chega ao fim também em computadores onde antes abortava com «ficheiro danificado»; em troca, o ficheiro de instalação é 23 megabytes maior.
### Chat e apoio de modelos

- Se uma referência a uma característica for ambígua, o chat para, destaca os candidatos na imagem e pergunta, indicando o corpo a que cada um pertence.
- Quando o chat distribui objetos por mesas de impressão, o resultado fica depois visível na imagem.
- Um achado sobre um conjunto aponta o corpo em questão e traz a sua ação; onde não há nenhuma, é uma simples indicação.
- O chat conhece as novas ações sobre características reconhecidas e executa-as quando pedido.
## 0.3.0

### Primeiros passos e orientação

- Quatro percursos guiados explicam os caminhos principais, desde o primeiro esboço até ao resultado pronto a imprimir.
- O ecrã inicial ocupa por completo até janelas pequenas ou estreitas, sem cartões cortados nem conteúdos tapados.
- Os projetos usados recentemente aparecem antes das visitas introdutórias e ficam assim mais rapidamente acessíveis.
- O ecrã inicial já não move a seleção sem pedido e pode ser usado inteiramente com rato e teclado.
- As opções *Novo*, *Abrir* e *Exemplos* estão organizadas com mais clareza e descrevem o destino antes de o abrir.
- A opinião e o apoio voluntário estão acessíveis no ecrã inicial, também por teclado e tecnologias de apoio.
- O chat continua utilizável mesmo com pouca altura da janela: a entrada mantém-se fixa em baixo e o conteúdo desloca-se.
- A barra de ferramentas superior mantém-se visível com projetos abertos e janelas estreitas, sem sair da área de trabalho.
- Um novo exemplo de desenho conduz diretamente ao percurso de esboço e complementa os projetos de exemplo existentes.
- O ecrã inicial tem um botão *Abrir modelo …*, e a área de largar ficheiros também pode ser clicada.
### Interface e utilização

- Os menus têm títulos bem visíveis e colunas de ícones alinhadas de forma uniforme.
- A visão geral dos comandos alinha atalhos e explicações, permitindo percorrer mais depressa as entradas longas.
- Os diálogos extensos usam colunas e larguras de campo uniformes.
- A antiga página conjunta para aderência, retração e filamento foi dividida em áreas de definições menores e com nomes claros.
- Todas as 56 definições de impressão podem ser pesquisadas pelas respetivas designações alemãs visíveis.
- A pesquisa também reconhece 146 termos comuns de slicers, entre os quais *perimeters* e *wall loops*.
- Os campos numéricos respondem corretamente a setas, incrementos e arredondamentos, sem alterar valores inesperadamente.
- Os controlos deslizantes têm um aspeto uniforme com um manípulo fácil de agarrar.
- A cor de destaque fica reservada ao botão principal; a ferramenta ativa distingue-se pelo seu rebordo e os controlos inativos ficam visualmente em segundo plano.
- Cálculos muito curtos evitam indicadores intermitentes; os médios mostram espera e os longos acrescentam progresso e cancelamento.
- As indicações mantêm-se numa linha quando há largura e mudam de linha de forma controlada em janelas estreitas.
- As pré-visualizações na árvore de objetos são suficientemente grandes para permitir reconhecer realmente as formas.
- A lista de filamentos desloca-se separadamente; *Adicionar filamento* e *Valores de impressão* continuam acessíveis com muitas bobinas.
- Os avisos e erros são legíveis sem transmitir o significado apenas pela cor do texto.
- Os campos de seleção desativados distinguem-se claramente dos campos ativos e selecionados.
- Um rato 3D (SpaceMouse) move o modelo nos seis eixos assim que é ligado; um botão do dispositivo enquadra tudo.
- A placa de impressão oculta-se com um clique ou Ctrl+Shift+D e assim fica até voltar a ser precisa.
### Desenho e introdução precisa

- Os círculos são introduzidos pelo diâmetro; um furo M3 pode assim ser criado diretamente com 3,2 mm.
- Uma restrição de diâmetro continua a ser uma expressão editável após resolver, guardar e voltar a abrir.
- As medidas podem ser editadas diretamente com duplo clique, sem o anterior e demorado percurso de seleção.
- A posição X, Y e Z, o ângulo e a escala podem ser introduzidos diretamente na barra de movimento.
- Uma introdução exata cria o mesmo passo reversível que um movimento com o rato.
- Na rotação ou escala exata, vários corpos selecionados usam um centro comum.
- Escape recua apenas um nível ao desenhar: linha atual, ferramenta atual e só depois o esboço completo.
- Refazer funciona agora mesmo com um esboço aberto.
- Um esboço vazio mostra uma indicação clicável que abre as formas básicas prontas.
- O botão das formas básicas tem o nome da ação do clique. As restantes formas encontram-se atrás da seta ao lado.
- A ferramenta de corte abre dentro do corpo, em vez de numa vista vazia fora do modelo.
- As vistas frontal, lateral, superior e opostas alinham-se corretamente com todos os seis eixos.
- A pega de arrastar mantém-se visível mesmo com a câmara rasante ou inclinada e mostra uma medida útil.
- A ferramenta de medição termina uma medição com uma resposta visível, em vez de parecer perder o resultado.
- Ao puxar para cima, a medida fica junto à estrutura de arame, e depois de largar todos os valores continuam editáveis no diálogo.
- As medidas ao desenhar seguem a grelha, não o ponteiro: vê-se a medida que realmente se obtém.
- As medidas de círculo alternam entre diâmetro e raio no próprio campo; a escolha vale no esboço e nos diálogos e fica guardada.
- Um círculo com centro fixo e diâmetro cotado conta como totalmente determinado; a linha de estado deixa de indicar uma medida em falta.
### Vista, histórico e edição de formas

- É possível mover em conjunto vários corpos selecionados.
- Vários corpos selecionados rodam em torno de um centro comum e mantêm as distâncias entre si.
- Depois de rodar, os corpos podem voltar corretamente à mesa de impressão no mesmo passo de trabalho.
- Os movimentos consecutivos do mesmo corpo são reunidos num passo compreensível do histórico.
- Os passos relacionados aparecem numa entrada expansível, em vez de sobrecarregarem o histórico com linhas isoladas.
- Uma ação contínua do utilizador pode ser totalmente anulada com um único comando Desfazer.
- As entradas do histórico mostram o seu tipo e um número de passo inequívoco.
- Os modelos descarregados e importados podem ser cortados imediatamente.
- Um clique num resultado da verificação conduz de forma fiável ao local, corpo ou passo do histórico afetado.
- Ao saltar para um resultado, a câmara enquadra o alvo em vez de terminar num grande plano cinzento.
- As faces designadas e indicações acompanham o corpo durante a disposição e o posicionamento.
- Ao modelar com o pincel, é indicado se os traços falham o modelo ou não produzem uma alteração imprimível.
- Um texto numa parede lateral fica horizontal e direito em vez de num ângulo qualquer; na face de cima e de baixo continua a mandar o ângulo definido.
- Se uma inscrição ficar dentro do corpo em vez de sobre ele, a operação diz-o e indica o caminho: clicar na face onde o texto deve assentar.
- Os corpos ocos mantêm a espessura de parede pretendida também em faces inclinadas e curvas.
- Um furo alargado de propósito mantém o seu nome e os seus ajustes em vez de contar como perdido no relatório.
- As esferas com muitíssimos segmentos continuam a ser uma malha manejável em vez de vinte milhões de triângulos.

### Blocos próprios e ficheiros de troca

- Os blocos próprios podem ser guardados num ficheiro local .solidon-part e adicionados novamente ao catálogo.
- Os ficheiros de bloco podem ser abertos, arrastados para a aplicação e importados pela associação de ficheiros do sistema.
- O nome e a extensão mostram de imediato que o ficheiro pertence ao Solidon.
- A importação, partilha e biblioteca local usam textos completos da interface nos seis idiomas.
- Antes de guardar, um bloco próprio pode ser composto por vários passos e valores editáveis.
- Ao partilhar, pode escolher entre uso livre, atribuição ou atribuição com partilha nas mesmas condições.
- Num bloco a que deu um nome, o seu nome prevalece sobre o nome incluído no ficheiro.
- A proveniência e as condições de partilha continuam rastreáveis ao trocar um bloco.
- Encaixes, olhais de dobradiça, ganchos para painéis perfurados e pés têm transições mais robustas, sem superfícies internas fechadas.
- Os cartões do catálogo mantêm a posição e a face selecionada enquanto carregam as pré-visualizações.
- A escada de tolerâncias marca cada degrau com o seu próprio número.
- Os ficheiros GLB exportados ficam de pé noutros programas em vez de deitados.

### Divisão, impressão e filamento

- A divisão automática privilegia interfaces resistentes e evita o anterior ponto fraco mais fino que podia ser escolhido.
- O tipo de ligação adequado é escolhido separadamente para cada corte e guardado como uma forma concreta.
- As indicações sobre ligações coladas permanecem associadas ao corte escolhido.
- A divisão automática responde de forma reproduzível a orientações alteradas e pode ser cancelada durante o cálculo.
- A pesquisa de orientação testa apenas posições realmente diferentes e cumpre o tempo previsto mesmo com corpos complexos.
- Os ficheiros 3MF grandes são reconhecidos e processados mais depressa sem alterar o resultado do ficheiro.
- O material, o ajuste e as tolerâncias seguem a bobina realmente escolhida ou a posição ocupada na impressora.
- O cabeçalho mostra o material realmente utilizado e já não oferece uma segunda seleção contraditória do material.
- O botão desativado *Guardar ficheiro de impressão* explica que o ficheiro só é criado durante o fatiamento.
- As reparações já feitas no mesmo fluxo de trabalho deixam de surgir depois como recomendações em aberto.
- Os furos para pinos abrem-se na divisão com um chanfro de entrada, e o ressalto de um bolso de encaixe fica na junta.
- Um diâmetro de pino escolhido à mão tem de caber na junta; se por isso ficar mais fino, o relatório di-lo.

### Relatório, estabilidade, plataformas e idiomas
- No Linux numa sessão Wayland, o Solidon arranca e mostra a vista 3D; se faltar uma biblioteca ao sistema, a aplicação arranca à mesma e indica qual falta.

- Os resultados semelhantes são agrupados sem perder a ligação aos corpos e locais afetados.
- Os números e medições no relatório têm designações completas, em vez de valores isolados incompreensíveis.
- Se uma reparação falhar, o corpo original inalterado é totalmente restaurado.
- Uma malha importada fechada já não é aberta pela remoção precipitada de um triângulo problemático.
- Os botões de ação do relatório já não mantêm discretamente na memória uma janela que foi fechada.
- Os blocos incluídos e a ativação carregam ao iniciar sem se bloquearem mutuamente.
- A vista 3D termina corretamente antes da janela, tornando o fecho mais fiável no Windows, Linux e macOS.
- No Windows 11 a barra de título segue o esquema de cores da aplicação; as outras plataformas mantêm-se inalteradas.
- Os botões padrão como Abrir, Guardar e Cancelar mudam imediatamente de idioma, sem reiniciar.
- Os nomes gerados de corpos e blocos mudam corretamente de idioma mesmo após usar conteúdos anteriormente em cache.
- As traduções e os valores dos relatórios estão ao mesmo nível em alemão, inglês, espanhol, francês, italiano e português.
- Uma peça sem ocorrências oferece no relatório diretamente o botão *Entregar ao slicer …*.
- Cada mapa de análise explica ao apontar o que mostra, e a pergunta da unidade ao importar nomeia as unidades por extenso.
- Uma peça que enche a mesa de impressão é lida em milímetros sem perguntar.
- Nervuras finas junto a placas grossas são reconhecidas como ponto fino, e as pontes são medidas na sua largura realmente livre.
- A uma peça que assenta sobre si própria não são recomendados suportes a partir da mesa.
- As recomendações de impressão verificam todas as velocidades, calculam a primeira camada com as suas próprias medidas e avisam de uma mesa ou câmara demasiado fria para o material.
- Abas sobrepostas mantêm cada uma o seu furo, e riscos finos não contam nem como furo nem como pino.
### Chat e apoio de modelos

- O chat apresenta o seu objetivo concreto e já não começa com um espaço vazio ou termos técnicos de modelos.
- Os contadores técnicos de tokens foram retirados da interface normal do cliente.
- Os avisos idênticos sobre detalhes de forma perdidos chegam ao assistente contados em vez de um a um.
- O diálogo de geração transforma texto ou imagem num modelo através de um ComfyUI local e insere-o na mesma cena editável.
- O fluxo TripoSG incluído cria um ficheiro GLB, que é depois reparado, dimensionado e verificado automaticamente para impressão.
- O Ollama local e o ComfyUI local processam um após o outro, para não ocuparem a placa gráfica em simultâneo.
- Após uma proposta do agente ou uma geração 3D, o Solidon liberta os modelos locais e a memória gráfica.
- Ao cancelar, o Solidon remove apenas a sua própria tarefa do ComfyUI; as outras tarefas em curso permanecem intactas.
- Antes da primeira utilização de um modelo na nuvem, o Solidon mostra claramente que conteúdos saem do computador.
- O diálogo dos programas adicionais mostra apenas o que ainda falta e descreve o estado do ComfyUI em palavras simples.
## 0.2.2


### Desenho e modelação

- No modo de esboço pode selecionar e arrastar pontos, linhas, círculos e contornos diretamente na vista. Uma marca e uma pega indicam também o que vai mover-se.
- O plano de desenho fica no espaço ao alternar entre as vistas de cima, frente e lado. Assim vê a posição real em vez da mesma imagem três vezes.
- Um retângulo pode ser concluído escrevendo a largura e a altura. As medidas ficam como restrições em vez de se perderem depois do desenho.
- Na vista de frente ou de lado, puxe um contorno fechado para lhe dar altura. A medida e a pré-visualização em arame crescem; um valor escrito fixa a altura exata.
- Puxe o contorno para fora para criar um corpo ou para dentro para criar uma bolsa visível. Uma seta e uma cruz tornam ambas as direções agarráveis.
- A pré-visualização mostra o bloco, cilindro ou corpo do esboço enquanto introduz as medidas. Antes, os corpos novos ficavam invisíveis até aplicar o passo.
- As ferramentas de desenho dizem o que fará o próximo clique. As restrições explicam o efeito e a seleção, e os graus de liberdade são descritos de forma clara.
- Cubo, cilindro, furo e esvaziamento aparecem uma só vez no menu. A caixa «Editar faces e arestas mais tarde» substitui a segunda entrada, antes chamada «exato».
- Esta caixa mantém disponíveis chanfros, arredondamentos, ângulos de saída, faces deslocadas e a exportação STEP. O diálogo nomeia a vantagem, não o motor de cálculo.
- Ao desenhar, a barra nomeia o passo seguinte: Elevar, Rebaixar ou Concluído. Se faltar um contorno fechado ou um corpo selecionado, também o indica.
- Uma restrição retira-se com um segundo clique no mesmo botão, e um clique direito sobre o ponto mostra o que depende dele. Antes, cada clique acrescentava outra até tudo bloquear.
- A barra de restrições mostra apenas o que combina com a seleção. Se nada estiver selecionado, está lá uma frase em vez de dez termos técnicos a cinzento.
- Os corpos básicos assentam «na mesa de impressão» em vez de «em Z = 0», e a ferramenta de desenho chama-se «curva», como aquilo que desenha.

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
- Os blocos estão no catálogo com imagens de pré-visualização em vez de como lista no menu. Um clique direito sobre a peça escolhida leva lá.
- O catálogo avisa antes de inserir quando falta o sítio no corpo. A maioria dos blocos precisa de uma face ou de um furo selecionado; antes o catálogo permitia o que a operação depois recusava.

### Impressão e filamento

- Cada bobina pode ter temperaturas, arrefecimento, retração e valores de material próprios. Esses valores mantêm-se quando muda o nível de qualidade.
- Os valores de cada bobina chegam ao ficheiro 3MF e ao slicer no lugar de material correto. Uma cor já não recebe por engano os valores de impressão de outra.
- No primeiro arranque, o Solidon importa os filamentos carregados no slicer com nome, tipo, cor e perfil do fabricante. Não precisa de voltar a criar as bobinas.
- Os exemplos incluídos já não substituem a impressora e o material escolhidos pelas definições usadas para criar as respetivas pré-visualizações.
- No Flatpak Linux, o Solidon encontra e inicia slicers do computador, incluindo AppImages. Ambos os programas conseguem aceder à pasta de trabalho partilhada.
- Ao dividir são colocados pinos de posicionamento numa metade e os furos correspondentes na outra. A mensagem indica quantos são ou avisa que a face de corte é pequena demais.
- Depois de dividir, as metades afastam-se. Os pinos e os furos já não desaparecem entre duas faces de corte coincidentes.
- Ao unir dois corpos, ambos mantêm a sua descrição de filamento com o nome. Antes, a descrição da segunda cor podia perder-se.
- Ao exportar para várias placas, as mudanças de cor são contadas por placa. Uma placa de um só material já não anuncia mudanças que não ocorrem na impressão.

- Se o slicer configurado falhar, a mensagem oferece a mudança para outro. Antes só restava exportar — mesmo com dois slicers a funcionar mesmo ao lado.
- O ficheiro de impressão pronto abre-se diretamente na janela do slicer, com os perfis dele. Qual entrega usa fica registado por projeto.
- O ficheiro de impressão é verificado contra a altura do modelo. Uma peça enterrada sob a mesa nota-se antes da impressão — não a meia altura na impressora.
- O ElegooSlicer volta a aceitar trabalhos. E se um slicer dispuser as peças por conta própria, o relatório di-lo em vez de substituir em silêncio a ocupação da mesa planeada.
- O relatório já não acumula medições antigas: uma nova passagem substitui o que mede de novo, o mesmo facto aparece uma só vez, e os avisos de volume nomeiam o objeto em vez de um número.
- Os perfis de slicer registados sabem a que slicer pertencem. Depois de uma mudança, nenhum perfil alheio passa para o programa novo.
- Um motivo de bloqueio sob as definições de impressão desaparece assim que deixa de valer. Antes, “precisa de um perfil de impressora” ficava ao lado de um botão há muito livre.

### Chat e geração 3D

- As definições separam claramente modelos na cloud e locais. Antes de introduzir uma chave da cloud explicam que dados saem do computador.
- A verificação de um gerador 3D lento já não prende a janela. Mostra o que está a ser verificado e como instalar os programas adicionais.
- A atribuição dos elementos detetados continua fluida em modelos grandes. Centenas de elementos são comparados em conjunto em vez de um a um.
- Os pedidos ao Ollama e ao ComfyUI no mesmo computador evitam o proxy da empresa. Um serviço local ativo já não é indicado por engano como inacessível.
- No Flatpak Linux, a instalação e o início de programas auxiliares decorrem no computador, não na sandbox. O ComfyUI também é encontrado nos locais habituais.
- O botão Gerar só está clicável quando o clique inicia mesmo alguma coisa. Se faltar algo, o diálogo diz o quê — com um botão que leva à solução.
- Se a geração falhar, a própria linha de erro do ComfyUI aparece no diálogo, junto com o passo em que aconteceu. É exatamente a linha de que se precisa ao pedir ajuda.
- Se um modelo de linguagem escrever a chamada como texto em vez de a executar, a proposta explica-o — com o caminho para “Verificar as ferramentas”. Antes ficava JSON em bruto na conversa.
- O manual tem uma página nova, “Que modelos o Solidon usa”: quais estão testados, de onde vêm e quanto demoram. Para o caminho a partir de texto diz que ficheiro pertence a que pasta.
- Um corpo gerado muito pequeno mostra o seu volume real em vez de “0 mm³” ao lado de “fechado”.
- Nos modelos de IA da geração escolhe por tarefa qual calcula — como no modelo de linguagem. “Automático” continua a ser a predefinição e toma o que serve.

### Vista e utilização

- A barra de parâmetros mantém as medidas compactas e visíveis. Unidade, limites e expressão podem ser alterados ali com anulação, sem esconder o próprio valor.
- Os cursores do Solidon seguem o tamanho configurado no sistema em Windows, macOS e Linux. O ponto de clique volta à ponta desenhada em vez de ficar ao lado.
- Passar o ponteiro e selecionar são marcados de forma claramente diferente. As cores de análise e diferenças continuam prioritárias sobre o realce do corpo inteiro.
- Menus, indicações e manual usam palavras coerentes para principiantes. Os termos especializados são explicados onde são necessários pela primeira vez.
- A janela Apoiar explica antes de abrir o PayPal que o pagamento é voluntário e não desbloqueia funções. Se o navegador falhar, o link pode ser copiado.
- Esvaziar e as outras ferramentas dependentes mostram apenas os campos usados pela variante escolhida e explicam de forma uniforme os valores ocultos.
- Os exemplos incluídos abrem com uma visita guiada. À direita indica passo a passo o que fazer e reconhece sozinha quando um passo está feito.
- As ações propostas para um erro mantêm-se ao guardar. Ao reabrir um projeto, antes restava apenas o erro, sem a saída.
- A procura de orientação examina cada posição uma só vez. As posições propostas várias vezes custavam tempo sem dar um resultado diferente.
- Os passos do histórico podem ser apagados e recuperados com Ctrl+Z. A pergunta anterior nomeia os passos que assentam no apagado.
- Um duplo clique num passo agrupado do histórico diz onde estão os passos individuais. Antes não fazia nada, embora as visitas guiadas ensinem justamente esse gesto.
- Se um ficheiro for recusado ao ser lido, o indicador de carregamento desaparece. Antes ficava como se ainda se calculasse um ficheiro que não tinha sido aceite.
- O Solidon arranca mais depressa e a análise de camadas calcula com mais rapidez. As grandes bibliotecas de cálculo só são carregadas quando há mesmo que calcular.

- As mensagens de erro mostram os dados a que as suas frases se referem. “O início da resposta está ao lado” — agora está mesmo, junto com endereço e fornecedor.
- Os conselhos “Reduzir triângulos” e “Abrir a página no navegador” agora são botões que fazem exatamente isso, em vez de frases que o descrevem.
- Quando um serviço não responde, o diálogo nomeia o endereço para ver no navegador e guarda a tentativa em “Detalhes”. Os avisos só apontam para botões que existem.
- As listas pendentes das barras sob a vista ficam abertas até escolher. Antes, uma lista podia fechar-se logo, porque deslizava de debaixo do ponteiro.
- O campo de espessura da barra de corte espera até acabar de escrever. Antes cortava a cada tecla — primeiro com 3 mm e depois com 30.
- Depois de abrir, o relatório pré-seleciona o primeiro aviso que oferece uma ação. “Pousar na mesa” fica logo ali como botão, sem ter de clicar primeiro na linha.
- O aviso sobre peças soltas muito pequenas agora oferece o botão «Remover as peças pequenas». Antes dizia apenas que nada foi apagado e deixava que você procurasse o caminho.
- As reparações já concluídas na importação aparecem como nota no relatório, não mais como aviso. Antes o relatório abria em amarelo num de cada dois modelos, sem nada a fazer.
- O aviso sobre a gestão de pacotes cancelada chama o botão pelo nome completo — nas seis línguas. “Detalhes” sozinho era uma pequena procura em cinco delas.

### Plataformas e correções

- Para Linux há agora uma AppImage além do Flatpak. Assim, o Solidon pode iniciar como um único ficheiro executável sem instalar Flatpak.
- Uma atualização do Windows iniciada pelo Solidon mostra apenas o progresso e volta a abrir o Solidon. Se iniciar o instalador à mão, mantém a opção de abertura na página final.
- O Flatpak Linux pode ser atualizado a partir do Solidon.
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
- Um bloco pode reunir várias peças. Assim pode guardar um modelo móvel ou montado como uma única entrada reutilizável do catálogo.
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
- Blocos próprios sem uma linha de código: escolha passos no histórico e coloque-os no catálogo como bloco — com campos próprios, pré-visualização e um intervalo de valores à sua escolha.
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
