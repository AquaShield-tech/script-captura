import platform
import socket
import time
import uuid
from datetime import datetime
import subprocess

import mysql.connector
import psutil
import matplotlib.pyplot as plt

banco = mysql.connector.connect(
    user="root",
    password="",
    host="localhost",
    database="aquashield"
)
cursor = banco.cursor()

# Deixe 0 para nao gravar porcentagem de rede sem referencia.
#Velocidade maxima que a rede atinge 
VELOCIDADE_REDE_MBPS = 1000
INTERVALO_CAPTURA = 5

#macNumero = uuid.getnode() - pega o endereço Mac da Máquina
macNumero = uuid.getnode()
macFormatado = ""
for i in range(5, -1, -1):
    parteMacTexto = "{:02x}".format((macNumero >> (i * 8)) & 0xff)
    if macFormatado == "":
        macFormatado = parteMacTexto
    else:
        macFormatado += ":" + parteMacTexto
macSemPontuacao = macFormatado.replace(":", "")


# utilizo o Banco de dados para pegar a unidade de medida
def obterIdMedidaPorcentagem():
    cursor.execute(
        "SELECT id FROM Medida WHERE unidade_medida = %s LIMIT 1",
        ("%",)
    )
    resultado = cursor.fetchone()

    if resultado is not None:
        return resultado[0]

#Cria a unidade de medida se não tiver cadastrada no banco de dados
    cursor.execute(
        "INSERT INTO Medida (unidade_medida) VALUES (%s)",
        ("%",)
    )
    banco.commit()
#retorna o ID recem criado
    return cursor.lastrowid

#Serve para ver obter o alerta passado pelo usuario, implementação futura quando o usuario conseguir definir o alerta da máquina 
#Se o alerta não for definido por padrão, ele gera um alerta quando passar de 80% de uso.
def obterIdAlerta():
    cursor.execute("SELECT id FROM Definicao_Alerta LIMIT 1")
    resultado = cursor.fetchone()

    if resultado is not None:
        return resultado[0]

    cursor.execute(
        "INSERT INTO Definicao_Alerta (valor_limite) VALUES (%s)",
        (80.0,)
    )
    banco.commit()

    return cursor.lastrowid


def verificarMaquina():
    #Verifica se a maquina já está cadastrada
    cursor.execute(
        "SELECT id FROM Maquina WHERE mac_address = %s LIMIT 1",
        (macSemPontuacao,)
    )
    resultado = cursor.fetchone()
    if resultado is not None:
        return resultado[0]
    #Verifica se existe uma Eta cadastrada
    cursor.execute("SELECT id FROM ETA LIMIT 1")
    resultadoETA = cursor.fetchone()
    if resultadoETA is None:
        print("Nenhuma ETA cadastrada. Cadastre uma ETA antes de capturar dados.")
        return None
    #Se existir uma ETA cadastrada, mas nenhuma máquina o código cria uma maquina
    cursor.execute(
        """
        INSERT INTO Maquina
        (hostname, mac_address, sistema_operacional, versao_so, data_cadastro, fk_eta)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            socket.gethostname()[:100],
            macSemPontuacao,
            platform.system()[:45],
            platform.release()[:10],
            datetime.now(),
            resultadoETA[0]
        )
    )
    #Salva e retorna o ID
    banco.commit()
    return cursor.lastrowid


def obterIdComponente(nomeComponente):
    #Obtem o id da unidade de medida
    idMedida = obterIdMedidaPorcentagem()
    cursor.execute(
        """
        SELECT id FROM Tipo_Componente
        WHERE tipo = %s AND fk_medida = %s LIMIT 1
        """,
        (nomeComponente, idMedida)
    )
    resultadoTipo = cursor.fetchone()
    #Se não existir ele cria 
    if resultadoTipo is None:
        cursor.execute(
            "INSERT INTO Tipo_Componente (tipo, fk_medida) VALUES (%s, %s)",
            (nomeComponente, idMedida)
        )
        banco.commit()
        idTipo = cursor.lastrowid
    else:
        idTipo = resultadoTipo[0]
    #Procura o componente correspondente
    cursor.execute(
        "SELECT id FROM Componentes WHERE fk_tipoComponente = %s LIMIT 1",
        (idTipo,)
    )
    resultadoComponente = cursor.fetchone()
    if resultadoComponente is not None:
        return resultadoComponente[0]
    #Cadastra o componente se ele não existir
    idAlerta = obterIdAlerta()
    cursor.execute(
        """
        INSERT INTO Componentes
        (valor_maximo, fk_tipoComponente, fk_definicaoAlerta)
        VALUES (%s, %s, %s)
        """,
        (100.0, idTipo, idAlerta)
    )
    banco.commit()
    return cursor.lastrowid

#Faz todas as verificações e garante que o status da máquina esteja Ativo
def garantirConfiguracao(idMaquina, idComponente):
    cursor.execute(
        """
        SELECT fk_statusMaquina FROM Configuracao
        WHERE fk_maquina = %s AND fk_componente = %s LIMIT 1
        """,
        (idMaquina, idComponente)
    )
    if cursor.fetchone() is not None:
        return

    cursor.execute(
        "SELECT id FROM Status_Maquina WHERE estado = %s LIMIT 1",
        ("Ativo",)
    )
    resultadoStatus = cursor.fetchone()
    if resultadoStatus is None:
        cursor.execute(
            "INSERT INTO Status_Maquina (estado) VALUES (%s)", ("Ativo",)
        )
        banco.commit()
        idStatus = cursor.lastrowid
    else:
        idStatus = resultadoStatus[0]

    cursor.execute(
        """
        INSERT INTO Configuracao (fk_maquina, fk_componente, fk_statusMaquina)
        VALUES (%s, %s, %s)
        """,
        (idMaquina, idComponente, idStatus)
    )
    banco.commit()

#Insere os dados da máquina no banco
def salvarLeitura(idMaquina, idComponente, valor):
    idMedida = obterIdMedidaPorcentagem()
    garantirConfiguracao(idMaquina, idComponente)
    cursor.execute(
        """
        INSERT INTO Leitura
        (valor, data_hora, fk_medida, configuracao_fk_maquina, configuracao_fk_componente)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (round(float(valor), 2), datetime.now(), idMedida, idMaquina, idComponente)
    )


def capturarRedePercentual():
    if VELOCIDADE_REDE_MBPS <= 0:
        return None, "Configure VELOCIDADE_REDE_MBPS no inicio do codigo."

    #Descobre quantos bytes foram transferidos em 1 segundo
    antes = psutil.net_io_counters(pernic=True)
    time.sleep(1)
    depois = psutil.net_io_counters(pernic=True)
    estatisticas = psutil.net_if_stats()
    maiorPercentual = 0
    encontrouInterface = False

    for nomeInterface, contadorDepois in depois.items():
        #Ignora interfaces desativadas
        if nomeInterface not in antes or nomeInterface not in estatisticas:
            continue
        
        if not estatisticas[nomeInterface].isup:
            continue
        nomeMinusculo = nomeInterface.lower()
        if nomeMinusculo == "lo" or "loopback" in nomeMinusculo:
            continue

        contadorAntes = antes[nomeInterface]
#Calcula quantos bytes foram transferidos por segundo
        bytesPorSegundo = (
            contadorDepois.bytes_sent - contadorAntes.bytes_sent
            + contadorDepois.bytes_recv - contadorAntes.bytes_recv
        )
        mbps = (bytesPorSegundo * 8) / 1000000
        percentual = min((mbps / VELOCIDADE_REDE_MBPS) * 100, 100)
        maiorPercentual = max(maiorPercentual, percentual)
        encontrouInterface = True

    if not encontrouInterface:
        return None, "Nenhuma interface de rede ativa foi encontrada."
    return round(maiorPercentual, 2), None
    

def capturarAtividadeDisco():
    try:
        resultado = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk | Where-Object {$_.Name -eq '_Total'}).PercentDiskTime"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if resultado.returncode != 0:
            print("Erro do PowerShell:", resultado.stderr.strip())
            return None

        valor = resultado.stdout.strip()

        if valor == "":
            print("O Windows nao retornou dados de atividade do disco.")
            return None

        return round(min(float(valor), 100.0), 2)

    except (ValueError, OSError, subprocess.TimeoutExpired) as erro:
        print("Erro ao consultar a atividade do disco:", erro)
        return None


def capturarDados():
    idMaquina = verificarMaquina()
    if idMaquina is None:
        return

    print("\n================================")
    print("       CAPTURA AQUASHIELD       ")
    print("================================")
    print("Maquina:", socket.gethostname())
    print("MAC:", macFormatado)

    usoCPU = psutil.cpu_percent(interval=1)
    usoMemoria = psutil.virtual_memory().percent
    usoDisco = capturarAtividadeDisco()

    if usoDisco is None:
        print("Nao foi possivel consultar a atividade do disco.")

    usoRede, erroRede = capturarRedePercentual()
    capturas = [
        ("Uso da CPU", usoCPU),
        ("Uso da Memoria", usoMemoria),
        ("Uso do Disco", usoDisco),
        ("Uso da Rede", usoRede)
    ]

    try:
        for nomeComponente, percentual in capturas:
            if percentual is None:
                print(nomeComponente + ": nao capturado.")
                if nomeComponente == "Uso da Rede" and erroRede:
                    print("Motivo:", erroRede)
                continue
            idComponente = obterIdComponente(nomeComponente)
            salvarLeitura(idMaquina, idComponente, percentual)
            print(nomeComponente + ": " + str(round(percentual, 2)) + "%")
        banco.commit()
        print("\nCapturas salvas no banco de dados.")
   
    except mysql.connector.Error as erro:
        banco.rollback()
        print("Erro ao salvar a captura:", erro)

def visualizarDados():
    idMaquina = verificarMaquina()
    if idMaquina is None:
        return
    #Explicando o SELECT 
    #Ele vai mostrar o tipo do componente, Data e hora da captura, Valor capturado e a unidade de medida do valor capturado
    #O From leitura 1 indica que a consulta começa da tabela leitura 
    #INNER JOIN Configuracao cfg - Define o relacionamento entre as tabelas e as duas condições precisão são verdadeiras
    #INNER JOIN Componentes - Indica qual componente está relacionado a configuração e aponta o seu ID
    #INNER JOIN Tipo_Component - Indica o tipo do componente
    #INNER JOIN Medida - Indica a unidade de medida do componente
    #WHERE cfg.fk_maquina = %s - Filtra os registros apenas da maquina selecionada 
    cursor.execute(
        """
        SELECT tc.tipo, l.data_hora, l.valor, m.unidade_medida
        FROM Leitura l
        INNER JOIN Configuracao cfg
            ON l.configuracao_fk_maquina = cfg.fk_maquina
            AND l.configuracao_fk_componente = cfg.fk_componente
        INNER JOIN Componentes c ON cfg.fk_componente = c.id
        INNER JOIN Tipo_Componente tc ON c.fk_tipoComponente = tc.id
        INNER JOIN Medida m ON l.fk_medida = m.id
        WHERE cfg.fk_maquina = %s
        ORDER BY l.data_hora DESC
        LIMIT 50
        """,
        (idMaquina,)
    )
    registros = cursor.fetchall()
    print("\n========== DADOS CAPTURADOS ==========")
    if not registros:
        print("Nenhum dado capturado para esta maquina.")
        return

    print("Componente | Data/Hora | Valor")
    print("--------------------------------------")
    for linha in registros:
        print(linha[0], "|", linha[1], "|", str(linha[2]) + " " + linha[3])


# Graficos

def gerarGrafico():
    idMaquina = verificarMaquina()
    if idMaquina is None:
        return
 #SELECT - Indica o tipo do componente, A data da captura e O valor capturado
 #O Inner Join relaciona as tabelas para descobrir o tipo do componente
 #WHERE cfg.fk_maquina = %s - Pega os dados apenas da máquina selecionada 
    cursor.execute(
        """
        SELECT tc.tipo, l.data_hora, l.valor
        FROM Leitura l
        INNER JOIN Configuracao cfg
            ON l.configuracao_fk_maquina = cfg.fk_maquina
            AND l.configuracao_fk_componente = cfg.fk_componente
        INNER JOIN Componentes c ON cfg.fk_componente = c.id
        INNER JOIN Tipo_Componente tc ON c.fk_tipoComponente = tc.id
        WHERE cfg.fk_maquina = %s
        ORDER BY l.data_hora DESC
        LIMIT 100
        """,
        (idMaquina,)
    )
    registros = cursor.fetchall()
    if not registros:
        print("Nao ha dados para gerar o gráfico.")
        return
    # Criando o dicionário para criar o gráfico
    dados = {}
    #Percorre os dados
    for nome, dataHora, valor in registros:
        if nome not in dados:
            #Cria uma lista para cada componente
            dados[nome] = {"datas": [], "valores": []}
        dados[nome]["datas"].append(dataHora)
        dados[nome]["valores"].append(float(valor))
    #Cria a área do gráfico 

    plt.figure(figsize=(12, 6))
    #Desenha as linhas do Gráfico
    #O for vai percorrer o dicionário e vai organizar os itens no gráfico
    for nome, valores in dados.items():
    #valores["datas"], Define as posições no eixo horizontal (y)#
    # valores["valores"], Define as posições do eixo verticar (x)#
    # marker="o", Desenha um circulo em cada ponto #
    # markersize=3, Define o tamnho dos circulos #
    # label=nome) Define o nome que vai aparecer na legenda 
        plt.plot(valores["datas"], valores["valores"], marker="o", markersize=3, label=nome)
    plt.title("Uso dos componentes ao longo do tempo")
    plt.xlabel("Data e hora")
    plt.ylabel("Uso (%)")
    plt.ylim(0, 100)
    plt.grid(True)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def capturaAutomatica():
    print("\n===== CAPTURA AUTOMATICA =====")
    print("Nova captura a cada", INTERVALO_CAPTURA, "segundos.")
    print("Pressione Ctrl+C para parar.")
    try:
        while True:
            capturarDados()
            time.sleep(INTERVALO_CAPTURA)
    except KeyboardInterrupt:
        print("\nCaptura automatica encerrada.")


# Menu
try:
    while True:
        print("\n==============================")
        print("          AQUASHIELD")
        print("==============================")
        print("MAC:", macFormatado)
        print("\n1 - Capturar dados")
        print("2 - Captura automatica")
        print("3 - Ver dados")
        print("4 - Gerar grafico")
        print("5 - Sair")
        opcao = input("Escolha uma opcao: ")

        if opcao == "1":
            capturarDados()
        elif opcao == "2":
            capturaAutomatica()
        elif opcao == "3":
            visualizarDados()
        elif opcao == "4":
            gerarGrafico()
        elif opcao == "5":
            print("Encerrando programa...")
            break
        else:
            print("Opcao invalida.")
except KeyboardInterrupt:
    print("\nPrograma interrompido.")
finally:
    try:
        cursor.close()
        banco.close()
    except mysql.connector.Error:
        pass
