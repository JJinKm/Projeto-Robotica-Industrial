# Projeto de Robótica Industrial

Interface ELO para demonstração Leader–Follower com UR3e (Leader) e UR5e (Follower).

## Abrir no Windows

1. Instale o Python 3.12 (64 bits) e clone ou baixe esta branch do repositório.
2. Na pasta `Projeto-Robotica-Industrial`, dê dois cliques em **`Iniciar_ELO.bat`**.
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

O painel Monitoramento tem duas abas: **Leituras**, com ângulos das juntas, pose TCP e força/torque; e **Visualização 3D + Câmeras**, com os modelos UR detalhados e duas prévias USB embutidas (webcam e câmera da garra). Clique em **Testar demo 3D** para animar os robôs com dados simulados, sem conectar nem enviar comandos aos robôs físicos. Tudo permanece dentro da janela do ELO. Arraste a divisória para ajustar o espaço entre o modelo 3D e os vídeos; use **Ampliar** para dar mais espaço a uma câmera dentro da aba e **Voltar** para restaurar a composição. As câmeras aparecem na lista quando o Windows as reconhece; selecione uma e clique em **Abrir câmera**. Cada prévia começa fechada.

Os arquivos visuais são baixados do repositório oficial [Universal_Robots_ROS2_Description](https://github.com/UniversalRobots/Universal_Robots_ROS2_Description), que contém os modelos e a licença aplicável. A postura 3D acompanha os ângulos simulados ou lidos pelo RTDE. O posicionamento dos elos segue a cadeia de juntas e as origens visuais do URDF; os robôs físicos podem ter diferenças de calibração.

O adaptador `ELO/rtde_telemetry.py` usa `RTDEReceive` para consultar dados. Não importa nem executa `ur_rtde.py`, e não envia comandos de movimento. A leitura real depende de o computador estar na rede dos controladores e de os endereços IP estarem corretos. Os botões da tela Operação controlam somente a simulação.
