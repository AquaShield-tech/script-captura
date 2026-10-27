import platform #captura dados do sistema operacional (Windows ou Linux)
import os #Serve como ponte para interagir com o sistema operacional (Windows ou Linux)
import socket #trabalha com conexões de rede e obtem informações relacionadas ao computador.
import time #trabalha com tempo e pausas na execução do programa.
import uuid #gera e trabalha com identificadores únicos.
from datetime import datetime #Data e hora
import subprocess #executar outros programas e comandos a partir do Python.

import mysql.connector #Conexão Mysql
import psutil #obtem informações sobre os recursos e o desempenho do sistema operacional.


banco = mysql.connector.connect(
    user="root",
    password="",
    host="localhost",
    database="aquashield"
)

cursor = banco.cursor()

INTERVALO_CAPTURA = 5

LIMITE_CPU_ATENCAO = 50.0
LIMITE_CPU_CRITICO = 80.0

LIMITE_MEMORIA_ATENCAO = 60.0
LIMITE_MEMORIA_CRITICO = 80.0

LIMITE_ARMAZENAMENTO_ATENCAO = 80.0
LIMITE_ARMAZENAMENTO_CRITICO = 90.0

LIMITE_LATENCIA_DISCO_ATENCAO = 25.0
LIMITE_LATENCIA_DISCO_CRITICO = 50.0


# Obtém o endereço MAC da máquina

macNumero = uuid.getnode()
macFormatado = ""

for i in range(5, -1, -1):
    parteMacTexto = "{:02x}".format((macNumero >> (i * 8)) & 0xff)

    if macFormatado == "":
        macFormatado = parteMacTexto
    else:
        macFormatado += ":" + parteMacTexto

macSemPontuacao = macFormatado.replace(":", "")


# Obtém o ID da unidade de medida de porcentagem
def obterIdMedidaPorcentagem():
    cursor.execute(
        "SELECT id FROM Medida WHERE unidade_medida = %s LIMIT 1",
        ("%",)
    )

    resultado = cursor.fetchone()

    if resultado is not None:
        return resultado[0]

    cursor.execute(
        "INSERT INTO Medida (unidade_medida) VALUES (%s)",
        ("%",)
    )

    banco.commit()

    return cursor.lastrowid


# Obtém o ID do alerta padrão
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


# Verifica se a máquina está cadastrada
def verificarMaquina():
    cursor.execute(
        "SELECT id FROM Maquina WHERE mac_address = %s LIMIT 1",
        (macSemPontuacao,)
    )

    resultado = cursor.fetchone()

    if resultado is not None:
        return resultado[0]

    cursor.execute("SELECT id FROM ETA LIMIT 1")

    resultadoETA = cursor.fetchone()

    if resultadoETA is None:
        print("Nenhuma ETA cadastrada. Cadastre uma ETA antes de capturar dados.")
        return None

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

    banco.commit()

    return cursor.lastrowid


# Obtém o ID de um componente

def obterIdComponente(nomeComponente):
    idMedida = obterIdMedidaPorcentagem()

    cursor.execute(
        """
        SELECT id FROM Tipo_Componente
        WHERE tipo = %s AND fk_medida = %s
        LIMIT 1
        """,
        (nomeComponente, idMedida)
    )

    resultadoTipo = cursor.fetchone()

    if resultadoTipo is None:
        cursor.execute(
            """
            INSERT INTO Tipo_Componente (tipo, fk_medida)
            VALUES (%s, %s)
            """,
            (nomeComponente, idMedida)
        )

        banco.commit()

        idTipo = cursor.lastrowid

    else:
        idTipo = resultadoTipo[0]

    cursor.execute(
        """
        SELECT id FROM Componentes
        WHERE fk_tipoComponente = %s
        LIMIT 1
        """,
        (idTipo,)
    )

    resultadoComponente = cursor.fetchone()

    if resultadoComponente is not None:
        return resultadoComponente[0]

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


# Garante que a máquina tenha uma configuração ativa para o componente

def garantirConfiguracao(idMaquina, idComponente):
    cursor.execute(
        """
        SELECT fk_statusMaquina FROM Configuracao
        WHERE fk_maquina = %s AND fk_componente = %s
        LIMIT 1
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
            "INSERT INTO Status_Maquina (estado) VALUES (%s)",
            ("Ativo",)
        )

        banco.commit()

        idStatus = cursor.lastrowid

    else:
        idStatus = resultadoStatus[0]

    cursor.execute(
        """
        INSERT INTO Configuracao
        (fk_maquina, fk_componente, fk_statusMaquina)
        VALUES (%s, %s, %s)
        """,
        (idMaquina, idComponente, idStatus)
    )

    banco.commit()


# Salva uma leitura no banco de dados

def salvarLeitura(idMaquina, idComponente, valor):
    idMedida = obterIdMedidaPorcentagem()

    garantirConfiguracao(idMaquina, idComponente)

    cursor.execute(
        """
        INSERT INTO Leitura
        (valor, data_hora, fk_medida,
        configuracao_fk_maquina, configuracao_fk_componente)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            round(float(valor), 2),
            datetime.now(),
            idMedida,
            idMaquina,
            idComponente
        )
    )


# Captura a atividade e a latência do disco no Windows

def capturarDadosDisco():
    try:
        comando = """
        $disco = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk |
        Where-Object { $_.Name -eq '_Total' }

        if ($null -eq $disco) {
            Write-Output 'ERRO'
        } else {
            Write-Output "$($disco.PercentDiskTime);$($disco.AvgDisksecPerRead * 1000);$($disco.AvgDisksecPerWrite * 1000)"
        }
        """

        resultado = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                comando
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if resultado.returncode != 0:
            print("Erro ao consultar o disco:", resultado.stderr.strip())
            return None, None, None

        valores = resultado.stdout.strip()

        if valores == "" or valores == "ERRO":
            print("O Windows nao retornou dados do disco.")
            return None, None, None

        partes = valores.split(";")

        if len(partes) != 3:
            return None, None, None

        atividade = float(partes[0])
        latenciaLeitura = float(partes[1])
        latenciaEscrita = float(partes[2])

        return (
            min(atividade, 100.0),
            latenciaLeitura,
            latenciaEscrita
        )

    except (ValueError, OSError, subprocess.TimeoutExpired) as erro:
        print("Erro ao consultar os dados do disco:", erro)
        return None, None, None


# Verifica os alertas dos componentes

def gerarAlertas(
    usoCPU,
    usoMemoria,
    armazenamentoDisco,
    espacoLivreGB,
    latenciaLeitura,
    latenciaEscrita
):
    alertasEncontrados = False

    print("\n========== ALERTAS AQUASHIELD ==========")

    # Alertas da CPU

    if usoCPU is not None:
        if usoCPU > LIMITE_CPU_CRITICO:
            print("\nALERTA CRITICO: utilizacao da CPU acima de 80%.")
            print("Uso atual:", round(usoCPU, 2), "%")
            alertasEncontrados = True

        elif usoCPU >= LIMITE_CPU_ATENCAO:
            print("\nATENCAO: utilizacao da CPU acima de 50%.")
            print("Uso atual:", round(usoCPU, 2), "%")
            alertasEncontrados = True

    # Alertas da memória RAM

    if usoMemoria is not None:
        if usoMemoria > LIMITE_MEMORIA_CRITICO:
            print("\nALERTA CRITICO: utilizacao da RAM acima de 80%.")
            print("Uso atual:", round(usoMemoria, 2), "%")
            alertasEncontrados = True

        elif usoMemoria >= LIMITE_MEMORIA_ATENCAO:
            print("\nATENCAO: utilizacao da RAM acima de 60%.")
            print("Uso atual:", round(usoMemoria, 2), "%")
            alertasEncontrados = True

    # Alertas de armazenamento

    if armazenamentoDisco is not None:
        if armazenamentoDisco >= LIMITE_ARMAZENAMENTO_CRITICO:
            print("\nALERTA CRITICO: disco com 90% ou mais de ocupacao.")
            print("Ocupacao atual:", round(armazenamentoDisco, 2), "%")
            alertasEncontrados = True

        elif armazenamentoDisco >= LIMITE_ARMAZENAMENTO_ATENCAO:
            print("\nATENCAO: disco com 80% ou mais de ocupacao.")
            print("Ocupacao atual:", round(armazenamentoDisco, 2), "%")
            alertasEncontrados = True

        if espacoLivreGB is not None:
            print("Espaco livre:", round(espacoLivreGB, 2), "GB")

    # Alertas de latência de leitura

    if latenciaLeitura is not None:
        if latenciaLeitura > LIMITE_LATENCIA_DISCO_CRITICO:
            print("\nALERTA CRITICO: latencia de leitura acima de 50 ms.")
            print("Latencia atual:", round(latenciaLeitura, 2), "ms")
            alertasEncontrados = True

        elif latenciaLeitura > LIMITE_LATENCIA_DISCO_ATENCAO:
            print("\nATENCAO: latencia de leitura acima de 25 ms.")
            print("Latencia atual:", round(latenciaLeitura, 2), "ms")
            alertasEncontrados = True

    # Alertas de latência de escrita

    if latenciaEscrita is not None:
        if latenciaEscrita > LIMITE_LATENCIA_DISCO_CRITICO:
            print("\nALERTA CRITICO: latencia de escrita acima de 50 ms.")
            print("Latencia atual:", round(latenciaEscrita, 2), "ms")
            alertasEncontrados = True

        elif latenciaEscrita > LIMITE_LATENCIA_DISCO_ATENCAO:
            print("\nATENCAO: latencia de escrita acima de 25 ms.")
            print("Latencia atual:", round(latenciaEscrita, 2), "ms")
            alertasEncontrados = True

    if not alertasEncontrados:
        print("Nenhum alerta foi identificado nesta captura.")


# Captura os dados dos componentes da máquina

def capturarDados():
    idMaquina = verificarMaquina()

    if idMaquina is None:
        return

    print("\n================================")
    print("       CAPTURA AQUASHIELD")
    print("================================")

    print("Maquina:", socket.gethostname())
    print("MAC:", macFormatado)

    usoCPU = psutil.cpu_percent(interval=1)

    usoMemoria = psutil.virtual_memory().percent

    # Captura a ocupação e o espaço livre do disco do sistema

    try:
        disco = psutil.disk_usage(os.path.abspath(os.sep))
        #O os.path.abspath(os.sep) identifica o caminho da raiz do sistema de arquivos.
        armazenamentoDisco = disco.percent

        espacoLivreGB = disco.free / (1024 ** 3)

    except OSError as erro:
        print("Nao foi possivel consultar o espaco do disco:", erro)

        armazenamentoDisco = None
        espacoLivreGB = None

    # Captura a atividade e a latência do disco

    (
        atividadeDisco,
        latenciaLeitura,
        latenciaEscrita
    ) = capturarDadosDisco()

    # Exibe os valores capturados

    print("\nUso da CPU:", round(usoCPU, 2), "%")
    print("Uso da memoria RAM:", round(usoMemoria, 2), "%")

    if armazenamentoDisco is not None:
        print(
            "Armazenamento ocupado (Uso do Disco:",
            str(round(armazenamentoDisco, 2)) + "%)"
        )

    if atividadeDisco is not None:
        print("Atividade do disco:", round(atividadeDisco, 2), "%")

    if latenciaLeitura is not None:
        print("Latencia de leitura:", round(latenciaLeitura, 2), "ms")

    if latenciaEscrita is not None:
        print("Latencia de escrita:", round(latenciaEscrita, 2), "ms")

    # Componentes que serao salvos no banco

    capturas = [
        ("Uso da CPU", usoCPU),
        ("Uso da Memoria", usoMemoria),
        ("Uso do Disco", armazenamentoDisco),
        ("Atividade do Disco", atividadeDisco)
    ]

    try:
        for nomeComponente, percentual in capturas:
            if percentual is None:
                print(nomeComponente + ": nao capturado.")
                continue

            idComponente = obterIdComponente(nomeComponente)

            salvarLeitura(
                idMaquina,
                idComponente,
                percentual
            )


        if espacoLivreGB is not None:
            print(
                "Espaco livre no disco:",
                round(espacoLivreGB, 2),
                "GB"
            )

        banco.commit()

        print("\nLimites de alertas:")
        print("CPU: atencao em 50%; critico acima de 80%.")
        print("RAM: atencao em 60%; critico acima de 80%.")
        print("Armazenamento: atencao em 80%; critico em 90%.")
        print("Latencia do disco: atencao acima de 25 ms; critico acima de 50 ms.")

        gerarAlertas(
            usoCPU,
            usoMemoria,
            armazenamentoDisco,
            espacoLivreGB,
            latenciaLeitura,
            latenciaEscrita
        )

        print("\nCapturas salvas no banco de dados.")

    except mysql.connector.Error as erro:
        banco.rollback()
        print("Erro ao salvar a captura:", erro)


# Exibe os dados salvos no banco

def visualizarDados():
    idMaquina = verificarMaquina()

    if idMaquina is None:
        return

    cursor.execute(
        """
        SELECT tc.tipo, l.data_hora, l.valor, m.unidade_medida
        FROM Leitura l
        INNER JOIN Configuracao cfg
            ON l.configuracao_fk_maquina = cfg.fk_maquina
            AND l.configuracao_fk_componente = cfg.fk_componente
        INNER JOIN Componentes c
            ON cfg.fk_componente = c.id
        INNER JOIN Tipo_Componente tc
            ON c.fk_tipoComponente = tc.id
        INNER JOIN Medida m
            ON l.fk_medida = m.id
        WHERE cfg.fk_maquina = %s
        ORDER BY l.data_hora DESC
        LIMIT 50
        """,
        (idMaquina,)
    )

    registros = cursor.fetchall()

    print("\nDados Capturados")

    if not registros:
        print("Nenhum dado capturado para esta maquina.")
        return

    print("Componente | Data/Hora | Valor")
    print("--------------------------------------")

    for linha in registros:
        print(
            linha[0],
            "|",
            linha[1],
            "|",
            str(linha[2]) + " " + linha[3]
        )

# Realiza capturas automaticamente

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


# Menu principal

try:
    while True:
        print("\n==============================")
        print("          AQUASHIELD")
        print("==============================")
        print("MAC:", macFormatado)
        print("\n1 - Capturar dados")
        print("2 - Captura automatica")
        print("3 - Ver dados")
        print("4- Sair")

        opcao = input("Escolha uma opcao: ")

        if opcao == "1":
            capturarDados()

        elif opcao == "2":
            capturaAutomatica()

        elif opcao == "3":
            visualizarDados()

        elif opcao == "4":
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
