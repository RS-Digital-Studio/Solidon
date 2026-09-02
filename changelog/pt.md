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

### Interface e utilização

- Os menus têm títulos bem visíveis e colunas de ícones alinhadas de forma uniforme.
- A visão geral dos comandos alinha atalhos e explicações, permitindo percorrer mais depressa as entradas longas.
- Os diálogos extensos usam colunas e larguras de campo uniformes.
- A antiga página conjunta para aderência, retração e filamento foi dividida em áreas de definições menores e com nomes claros.
- Todas as 56 definições de impressão podem ser pesquisadas pelas respetivas designações alemãs visíveis.
- A pesquisa também reconhece 146 termos comuns de fatiadores, entre os quais *perimeters* e *wall loops*.
- Os campos numéricos respondem corretamente a setas, incrementos e arredondamentos, sem alterar valores inesperadamente.
- Os controlos deslizantes têm um aspeto uniforme com um manípulo fácil de agarrar.
- A cor de destaque fica reservada ao botão principal; a ferramenta ativa distingue-se pelo seu rebordo e os controlos inativos ficam visualmente em segundo plano.
- Cálculos muito curtos evitam indicadores intermitentes; os médios mostram espera e os longos acrescentam progresso e cancelamento.
- As indicações mantêm-se numa linha quando há largura e mudam de linha de forma controlada em janelas estreitas.
- As pré-visualizações na árvore de objetos são suficientemente grandes para permitir reconhecer realmente as formas.
- A lista de filamentos desloca-se separadamente; *Adicionar filamento* e *Valores de impressão* continuam acessíveis com muitas bobinas.
- Os avisos e erros são legíveis sem transmitir o significado apenas pela cor do texto.
- Os campos de seleção desativados distinguem-se claramente dos campos ativos e selecionados.

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

### Relatório, estabilidade, plataformas e idiomas

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
