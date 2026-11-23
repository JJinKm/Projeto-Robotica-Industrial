# Projeto de Robótica Industrial

Interface AEGIS para inspeção robótica remota, com UR3e (Leader) e UR5e (Follower).

## Abrir no Windows

1. Instale o Python 3.12 (64 bits) e clone ou baixe esta branch do repositório.
2. Na pasta `Projeto-Robotica-Industrial`, dê dois cliques em **`Iniciar_ELO.bat`** para abrir o AEGIS.
3. Na primeira abertura, o iniciador cria um ambiente Python curto em `%LOCALAPPDATA%\ELO\elo-rtde-env`, instala as dependências listadas em `requirements.txt` e baixa as malhas 3D UR3e/UR5e para `%LOCALAPPDATA%\ELO\models`. Essa etapa precisa de internet.
4. Nas próximas vezes, dê dois cliques no mesmo arquivo.

O iniciador não altera os arquivos dos robôs e não inicia conexão RTDE nem câmera sozinho. Para ver a demonstração, abra a tela **Operação** e inicie a simulação. Para tentar ler dados reais, use **Monitoramento → Leituras → Conectar para ler medidas**.

## Abrir pelo terminal

No PowerShell, na pasta raiz do repositório:

```powershell
py -3.12 -m venv "$env:LOCALAPPDATA\ELO\elo-rtde-env"
& "$env:LOCALAPPDATA\ELO\elo-rtde-env\Scripts\Activate.ps1"
python -m pip install -r requirements.txt
python .\ELO\Projeto_Robotica.py
```

Se o ambiente já estiver preparado, basta ativá-lo e executar o último comando.

## Visualização e telemetria

O AEGIS usa uma identidade visual verde-escura e tem as áreas Início, Dashboard, Operação (com parâmetros), Monitoramento e Configurações. Na tela **Operação**, Iniciar, Pausar/Retomar e Home aparecem juntos; Parar e o ajuste de velocidade foram removidos. A escala continua disponível. O botão Home pede confirmação. O painel Monitoramento tem duas abas: **Telemetria**, com ângulos das juntas, pose TCP e força/torque; e **Câmeras e visualização 3D**, com os modelos UR e duas prévias USB embutidas (webcam e câmera da garra). Clique em **Testar demo 3D** para animar os robôs com dados simulados, sem conectar nem enviar comandos aos robôs físicos. Arraste a divisória para ajustar o espaço entre o modelo 3D e os vídeos; use **Ampliar** para abrir uma câmera em tela cheia e **Voltar** para restaurar a composição. As câmeras aparecem na lista quando o Windows as reconhece; selecione uma e clique em **Abrir câmera**. Cada prévia começa fechada.

Ao ampliar uma câmera, a interface entra em tela cheia e oculta a barra lateral. A outra câmera e os modelos dos dois robôs aparecem em janelas PiP independentes que podem ser arrastadas e redimensionadas, inclusive para um segundo monitor. Clique em **Ampliar** na outra câmera PiP para torná-la a principal. Pressione **Esc** ou use **Voltar ao monitoramento** para sair. Na tela Operação, Home retorna os modelos simulados à pose inicial após confirmação; não envia movimento aos robôs físicos.

Os arquivos visuais são baixados do repositório oficial [Universal_Robots_ROS2_Description](https://github.com/UniversalRobots/Universal_Robots_ROS2_Description), que contém os modelos e a licença aplicável. A postura 3D acompanha os ângulos simulados ou lidos pelo RTDE. O posicionamento dos elos segue a cadeia de juntas e as origens visuais do URDF; os robôs físicos podem ter diferenças de calibração.

O adaptador `ELO/rtde_telemetry.py` usa `RTDEReceive` para consultar dados. Não importa nem executa `ur_rtde.py`, e não envia comandos de movimento. A leitura real depende de o computador estar na rede dos controladores e de os endereços IP estarem corretos. Os sinais `iniciar_solicitado`, `pausar_retomar_solicitado` e `home_solicitado` são emitidos pelos botões após o clique (Home apenas depois da confirmação). Eles são pontos de integração para o controlador do Joshua; não têm conexão com um controlador físico nesta versão. Exemplo de ligação: `app.iniciar_solicitado.connect(controlador.iniciar)`. A logo AEGIS fica em `ELO/assets/aegis_logo.png`.
