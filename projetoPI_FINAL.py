import psutil
import time
import mysql.connector
import socket
import uuid
import msvcrt
import usb.core
import usb.util
import libusb_package

# Grupo 4

# Danilo 
# Alicia 
# Rodrigo 
# Melissa 
# Matheus Bernardino

banco = mysql.connector.connect(
    user='root',
    password='',
    host='localhost',
    database='aquashield'
)

cursor = banco.cursor()

backendUSB = libusb_package.get_libusb1_backend()

macNumero = uuid.getnode()
macFormatado = ""

for i in range(5, -1, -1):
    parteMac = (macNumero >> (i * 8)) & 0xff
    parteMacTexto = "{:02x}".format(parteMac)

    if macFormatado == "":
        macFormatado = parteMacTexto
    else:
        macFormatado = macFormatado + ":" + parteMacTexto

macSemPontuacao = macFormatado.replace(":", "")

print("Endereço MAC:", macFormatado)


def verificarMaquina():
    comando = """
        SELECT idMaquina
        FROM maquina
        WHERE IPMac = %s
        LIMIT 1
    """

    cursor.execute(comando, (macSemPontuacao,))
    resultado = cursor.fetchone()

    if resultado != None:
        return resultado[0]

    comando = """
        SELECT MAX(numeracao)
        FROM maquina
    """

    cursor.execute(comando)
    resultado = cursor.fetchone()
    ultimaNumeracao = resultado[0]

    if ultimaNumeracao is None:
        novaNumeracao = 1
    else:
        novaNumeracao = ultimaNumeracao + 1

    comando = """
        INSERT INTO maquina
        (numeracao, IPMac, fkEmpresa)
        VALUES (%s, %s, %s)
    """

    cursor.execute(comando, (novaNumeracao, macSemPontuacao, 1))
    banco.commit()

    return cursor.lastrowid


def obterNumeracaoMaquina(idMaquina):
    comando = """
        SELECT numeracao
        FROM maquina
        WHERE idMaquina = %s
    """

    cursor.execute(comando, (idMaquina,))
    resultado = cursor.fetchone()

    if resultado != None:
        return resultado[0]

    return None


def verificarComponente(nomeComponente, unidadeMedida):
    comando = """
        SELECT idComponente
        FROM componente
        WHERE nomeComponente = %s
        LIMIT 1
    """

    cursor.execute(comando, (nomeComponente,))
    resultado = cursor.fetchone()

    if resultado != None:
        return resultado[0]

    comando = """
        INSERT INTO componente
        (nomeComponente, unidadeMedida)
        VALUES (%s, %s)
    """

    cursor.execute(comando, (nomeComponente, unidadeMedida))
    banco.commit()

    return cursor.lastrowid


def BancoRegistro(fkMaquina, fkComponente, valorCaptura, valorMaximo):
    comando = """
        INSERT INTO registro
        (fkMaquina, fkComponente, valorCaptura, valorMaximo)
        VALUES (%s, %s, %s, %s)
    """

    valores = (
        fkMaquina,
        fkComponente,
        valorCaptura,
        valorMaximo
    )

    cursor.execute(comando, valores)


def BancoAlerta(fkMaquina, fkComponente, descricao, nivel):
    comando = """
        INSERT INTO alertas
        (fkMaquina, fkComponente, descricao, nivel)
        VALUES (%s, %s, %s, %s)
    """

    valores = (
        fkMaquina,
        fkComponente,
        descricao,
        nivel
    )

    cursor.execute(comando, valores)


def registrarAlertaSeNecessario(status, fkMaquina, fkComponente, descricao):
    if status != "BOM":
        BancoAlerta(fkMaquina, fkComponente, descricao, status)


def classificarTemperaturaCPU(temperatura):
    if temperatura <= 70:
        return "BOM"
    elif temperatura <= 85:
        return "ATENÇÃO"
    else:
        return "CRÍTICO"


def classificarUsoCPU(porcentagemUso):
    if porcentagemUso <= 70:
        return "BOM"
    elif porcentagemUso <= 95:
        return "ATENÇÃO"
    else:
        return "CRÍTICO"


def classificarFrequenciaCPU(frequenciaMHz):

    frequenciaGHz = frequenciaMHz / 1000

    if frequenciaGHz >= 0.79 and frequenciaGHz <= 1.5:
        return "CRÍTICO"
    elif frequenciaGHz > 1.5 and frequenciaGHz <= 2.5:
        return "BOM"
    else:
        return "ATENÇÃO"


def classificarMemoriaUsadaPercentual(percentualUsado):
    if percentualUsado <= 75:
        return "BOM"
    elif percentualUsado <= 90:
        return "ATENÇÃO"
    else:
        return "CRÍTICO"


def classificarMemoriaDisponivelPercentual(percentualDisponivel):
    if percentualDisponivel > 25:
        return "BOM"
    elif percentualDisponivel >= 10:
        return "ATENÇÃO"
    else:
        return "CRÍTICO"


def classificarDiscoUsoPercentual(percentualUso):
    if percentualUso <= 50:
        return "BOM"
    elif percentualUso <= 90:
        return "ATENÇÃO"
    else:
        return "CRÍTICO"


def classificarDiscoLivrePercentual(percentualLivre):
    if percentualLivre > 20:
        return "BOM"
    elif percentualLivre >= 10:
        return "ATENÇÃO"
    else:
        return "CRÍTICO"


# ===========================================================================


def capturaMemoria(idMaquina):
    memoria = psutil.virtual_memory()

    memoria_usada = round(memoria.used / (1024 ** 3))
    memoria_disponivel = round(memoria.available / (1024 ** 3))
    memoria_total = round(memoria.total / (1024 ** 3))

    percentualUsado = memoria.percent
    percentualDisponivel = (memoria.available / memoria.total) * 100

    statusUsada = classificarMemoriaUsadaPercentual(percentualUsado)
    statusDisponivel = classificarMemoriaDisponivelPercentual(percentualDisponivel)

    idComponenteUsada = verificarComponente("Memória Usada", "GB")
    idComponenteDisponivel = verificarComponente("Memória Disponível", "GB")

    BancoRegistro(idMaquina, idComponenteUsada, memoria_usada, memoria_total)
    BancoRegistro(idMaquina, idComponenteDisponivel, memoria_disponivel, memoria_total)

    descricaoUsada = "Memória usada em " + str(round(percentualUsado, 1)) + "%"
    descricaoDisponivel = "Memória disponível em " + str(round(percentualDisponivel, 1)) + "%"

    registrarAlertaSeNecessario(statusUsada, idMaquina, idComponenteUsada, descricaoUsada)
    registrarAlertaSeNecessario(statusDisponivel, idMaquina, idComponenteDisponivel, descricaoDisponivel)

    print()
    print("===== MEMÓRIA =====")
    print("Memória usada:", memoria_usada, "GB", "(", round(percentualUsado, 1), "%) -", statusUsada)
    print("Memória disponível:", memoria_disponivel, "GB", "(", round(percentualDisponivel, 1), "%) -", statusDisponivel)


def capturaDisco(idMaquina):
    disco = psutil.disk_usage('C:\\')

    discoUso = round(disco.used / (1024 ** 3))
    espacoLivre = round(disco.free / (1024 ** 3))
    discoTotal = round(disco.total / (1024 ** 3))

    percentualUso = disco.percent
    percentualLivre = (disco.free / disco.total) * 100

    statusUso = classificarDiscoUsoPercentual(percentualUso)
    statusLivre = classificarDiscoLivrePercentual(percentualLivre)

    idComponenteUso = verificarComponente("Disco Usado", "GB")
    idComponenteLivre = verificarComponente("Espaço Livre", "GB")

    BancoRegistro(idMaquina, idComponenteUso, discoUso, discoTotal)
    BancoRegistro(idMaquina, idComponenteLivre, espacoLivre, discoTotal)

    descricaoUso = "Disco usado em " + str(round(percentualUso, 1)) + "%"
    descricaoLivre = "Espaço livre em " + str(round(percentualLivre, 1)) + "%"

    registrarAlertaSeNecessario(statusUso, idMaquina, idComponenteUso, descricaoUso)
    registrarAlertaSeNecessario(statusLivre, idMaquina, idComponenteLivre, descricaoLivre)

    print()
    print("===== DISCO =====")
    print("Disco usado:", discoUso, "GB", "(", round(percentualUso, 1), "%) -", statusUso)
    print("Espaço livre:", espacoLivre, "GB", "(", round(percentualLivre, 1), "%) -", statusLivre)


def capturaTemperaturaCPU():

    temperatura = 0

    try:
        sensores = psutil.sensors_temperatures()
    except AttributeError:
        print("Aviso: leitura de temperatura via psutil não é suportada neste SO.")
        return temperatura

    if not sensores:
        print("Aviso: nenhum sensor de temperatura foi encontrado nesta máquina.")
        return temperatura

    nomesPrioritarios = ("coretemp", "k10temp", "cpu_thermal", "acpitz")

    for nomeSensor in nomesPrioritarios:
        if nomeSensor in sensores and len(sensores[nomeSensor]) > 0:
            temperatura = sensores[nomeSensor][0].current
            return temperatura

    chaves = list(sensores.keys())
    primeiraChave = chaves[0]

    if len(sensores[primeiraChave]) > 0:
        temperatura = sensores[primeiraChave][0].current

    return temperatura

def capturaCPU(idMaquina):
    temperatura = capturaTemperaturaCPU()

    frequencia = psutil.cpu_freq()

    if frequencia != None:
        frequenciaAtual = frequencia.current

        if frequencia.max:
            frequenciaMaxima = frequencia.max
        else:
            frequenciaMaxima = None
    else:
        frequenciaAtual = 0
        frequenciaMaxima = None

    porcentagemUso = psutil.cpu_percent(
        interval=1
    )

    statusTemperatura = classificarTemperaturaCPU(temperatura)
    statusFrequencia = classificarFrequenciaCPU(frequenciaAtual)
    statusUso = classificarUsoCPU(porcentagemUso)

    idComponenteTemperatura = verificarComponente("Temperatura", "°C")
    idComponenteFrequencia = verificarComponente("Frequência", "MHz")
    idComponenteUso = verificarComponente("Uso CPU", "%")

    BancoRegistro(idMaquina, idComponenteTemperatura, temperatura, None)
    BancoRegistro(idMaquina, idComponenteFrequencia, frequenciaAtual, frequenciaMaxima)
    BancoRegistro(idMaquina, idComponenteUso, porcentagemUso, 100)

    descricaoTemperatura = "Temperatura da CPU em " + str(round(temperatura, 2)) + "°C"
    descricaoFrequencia = "Frequência da CPU em " + str(round(frequenciaAtual, 2)) + "MHz"
    descricaoUso = "Uso da CPU em " + str(porcentagemUso) + "%"

    registrarAlertaSeNecessario(statusTemperatura, idMaquina, idComponenteTemperatura, descricaoTemperatura)
    registrarAlertaSeNecessario(statusFrequencia, idMaquina, idComponenteFrequencia, descricaoFrequencia)
    registrarAlertaSeNecessario(statusUso, idMaquina, idComponenteUso, descricaoUso)

    print()
    print("===== PROCESSADOR =====")
    print("Temperatura:", round(temperatura, 2), "°C -", statusTemperatura)
    print("Frequência:", round(frequenciaAtual, 2), "MHz -", statusFrequencia)
    print("Uso:", porcentagemUso, "% -", statusUso)


def capturaUSB(idMaquina):
    dispositivosConectados = usb.core.find(find_all=True, backend=backendUSB)

    nomesConectados = []

    for dispositivo in dispositivosConectados:
        nomeDispositivo = None

        try:
            nomeDispositivo = usb.util.get_string(dispositivo, dispositivo.iProduct)
        except:
            nomeDispositivo = None

        if nomeDispositivo == None or nomeDispositivo == "":
            nomeDispositivo = "USB " + str(dispositivo.idVendor) + ":" + str(dispositivo.idProduct)

        nomesConectados.append(nomeDispositivo)

        idComponenteUSB = verificarComponente(nomeDispositivo, "USB")

        BancoRegistro(idMaquina, idComponenteUSB, "TRUE", None)

        print("USB conectada:", nomeDispositivo)

    # Verifica as USBs que já foram cadastradas antes, mas que agora não
    # apareceram na lista de dispositivos conectados (ou seja, foram desconectadas)
    comando = """
        SELECT nomeComponente
        FROM componente
        WHERE unidadeMedida = %s
    """

    cursor.execute(comando, ("USB",))
    componentesUSBCadastrados = cursor.fetchall()

    for linha in componentesUSBCadastrados:
        nomeComponenteCadastrado = linha[0]

        if nomeComponenteCadastrado not in nomesConectados:
            idComponenteUSB = verificarComponente(nomeComponenteCadastrado, "USB")

            BancoRegistro(idMaquina, idComponenteUSB, "FALSE", None)

            print("USB desconectada:", nomeComponenteCadastrado)

    print()
    print("===== USB =====")
    print("Total de USBs conectadas agora:", len(nomesConectados))


def capturarDados():
    idMaquina = verificarMaquina()
    numeracaoMaquina = obterNumeracaoMaquina(idMaquina)

    print()
    print("================================")
    print("        DADOS DA MÁQUINA")
    print("================================")

    print("Máquina número:", numeracaoMaquina)
    print("ID da máquina:", idMaquina)

    capturaCPU(idMaquina)
    capturaMemoria(idMaquina)
    capturaDisco(idMaquina)
    capturaUSB(idMaquina)

    banco.commit()

    print()
    print("================================")
    print("DADOS CAPTURADOS COM SUCESSO!")
    print("================================")


def atualizarDados():
    print()
    print("===== ATUALIZAR =====")

    idRegistro = input("Digite o ID do registro (idRegistro): ")
    novoValor = input("Digite o novo valor de captura: ")

    comando = """
        UPDATE registro
        SET valorCaptura = %s
        WHERE idRegistro = %s
    """

    cursor.execute(
        comando,
        (novoValor, idRegistro)
    )

    banco.commit()

    print()
    print("REGISTRO ATUALIZADO COM SUCESSO!")


def deletarDados():
    print()
    print("===== DELETAR =====")

    idRegistro = input("Digite o ID do registro (idRegistro): ")

    comando = """
        DELETE FROM registro
        WHERE idRegistro = %s
    """

    cursor.execute(
        comando,
        (idRegistro,)
    )

    banco.commit()

    print()
    print("REGISTRO DELETADO COM SUCESSO!")


# ===================== VISUALIZAÇÃO =====================

def buscarRegistrosComponente(idMaquina, nomeComponente):
    comando = """
        SELECT idRegistro, dtHora, valorCaptura, valorMaximo
        FROM registro
        INNER JOIN componente ON registro.fkComponente = componente.idComponente
        WHERE fkMaquina = %s AND nomeComponente = %s
        ORDER BY dtHora DESC
    """

    cursor.execute(comando, (idMaquina, nomeComponente))
    registros = cursor.fetchall()

    return registros


def calcularPercentual(valorCaptura, valorMaximo):
    if valorMaximo is None:
        return 0

    if valorMaximo == 0:
        return 0

    percentual = (float(valorCaptura) / float(valorMaximo)) * 100

    return percentual


def visualizarMemoria(idMaquina):
    registrosUsada = buscarRegistrosComponente(idMaquina, "Memória Usada")
    registrosDisponivel = buscarRegistrosComponente(idMaquina, "Memória Disponível")

    print()
    print("===== HISTÓRICO DE MEMÓRIA =====")

    print()
    print("-- Memória Usada (GB) --")

    if len(registrosUsada) == 0:
        print("Nenhum registro encontrado.")
    else:
        print("ID | Data/Hora | Usada (GB) | Total (GB) | Status")

        for linha in registrosUsada:
            idRegistro = linha[0]
            dtHora = linha[1]
            valorCaptura = linha[2]
            valorMaximo = linha[3]

            percentual = calcularPercentual(valorCaptura, valorMaximo)
            status = classificarMemoriaUsadaPercentual(percentual)

            print(idRegistro, "|", dtHora, "|", valorCaptura, "|", valorMaximo, "|", status)

    print()
    print("-- Memória Disponível (GB) --")

    if len(registrosDisponivel) == 0:
        print("Nenhum registro encontrado.")
    else:
        print("ID | Data/Hora | Disp. (GB) | Total (GB) | Status")

        for linha in registrosDisponivel:
            idRegistro = linha[0]
            dtHora = linha[1]
            valorCaptura = linha[2]
            valorMaximo = linha[3]

            percentual = calcularPercentual(valorCaptura, valorMaximo)
            status = classificarMemoriaDisponivelPercentual(percentual)

            print(idRegistro, "|", dtHora, "|", valorCaptura, "|", valorMaximo, "|", status)


def visualizarDisco(idMaquina):
    registrosUso = buscarRegistrosComponente(idMaquina, "Disco Usado")
    registrosLivre = buscarRegistrosComponente(idMaquina, "Espaço Livre")

    print()
    print("===== HISTÓRICO DE DISCO =====")

    print()
    print("-- Disco Usado (GB) --")

    if len(registrosUso) == 0:
        print("Nenhum registro encontrado.")
    else:
        print("ID | Data/Hora | Usado (GB) | Total (GB) | Status")

        for linha in registrosUso:
            idRegistro = linha[0]
            dtHora = linha[1]
            valorCaptura = linha[2]
            valorMaximo = linha[3]

            percentual = calcularPercentual(valorCaptura, valorMaximo)
            status = classificarDiscoUsoPercentual(percentual)

            print(idRegistro, "|", dtHora, "|", valorCaptura, "|", valorMaximo, "|", status)

    print()
    print("-- Espaço Livre (GB) --")

    if len(registrosLivre) == 0:
        print("Nenhum registro encontrado.")
    else:
        print("ID | Data/Hora | Livre (GB) | Total (GB) | Status")

        for linha in registrosLivre:
            idRegistro = linha[0]
            dtHora = linha[1]
            valorCaptura = linha[2]
            valorMaximo = linha[3]

            percentual = calcularPercentual(valorCaptura, valorMaximo)
            status = classificarDiscoLivrePercentual(percentual)

            print(idRegistro, "|", dtHora, "|", valorCaptura, "|", valorMaximo, "|", status)


def visualizarProcessador(idMaquina):
    registrosTemperatura = buscarRegistrosComponente(idMaquina, "Temperatura")
    registrosFrequencia = buscarRegistrosComponente(idMaquina, "Frequência")
    registrosUso = buscarRegistrosComponente(idMaquina, "Uso CPU")

    print()
    print("===== HISTÓRICO DO PROCESSADOR =====")
    print("(Se a Temp. aparecer como 0, verifique se há sensores compatíveis via psutil.sensors_temperatures() nesta máquina)")

    print()
    print("-- Temperatura (°C) --")

    if len(registrosTemperatura) == 0:
        print("Nenhum registro encontrado.")
    else:
        print("ID | Data/Hora | Temp(°C) | Status")

        for linha in registrosTemperatura:
            idRegistro = linha[0]
            dtHora = linha[1]
            valorCaptura = linha[2]

            status = classificarTemperaturaCPU(float(valorCaptura))

            print(idRegistro, "|", dtHora, "|", valorCaptura, "|", status)

    print()
    print("-- Frequência (MHz) --")

    if len(registrosFrequencia) == 0:
        print("Nenhum registro encontrado.")
    else:
        print("ID | Data/Hora | Freq(MHz) | Status")

        for linha in registrosFrequencia:
            idRegistro = linha[0]
            dtHora = linha[1]
            valorCaptura = linha[2]

            status = classificarFrequenciaCPU(float(valorCaptura))

            print(idRegistro, "|", dtHora, "|", valorCaptura, "|", status)

    print()
    print("-- Uso (%) --")

    if len(registrosUso) == 0:
        print("Nenhum registro encontrado.")
    else:
        print("ID | Data/Hora | Uso(%) | Status")

        for linha in registrosUso:
            idRegistro = linha[0]
            dtHora = linha[1]
            valorCaptura = linha[2]

            status = classificarUsoCPU(float(valorCaptura))

            print(idRegistro, "|", dtHora, "|", valorCaptura, "|", status)


def visualizarUSB(idMaquina):
    comando = """
        SELECT DISTINCT nomeComponente
        FROM componente
        INNER JOIN registro ON componente.idComponente = registro.fkComponente
        WHERE unidadeMedida = %s AND fkMaquina = %s
    """

    cursor.execute(comando, ("USB", idMaquina))
    dispositivosUSB = cursor.fetchall()

    print()
    print("===== HISTÓRICO DE USB =====")

    if len(dispositivosUSB) == 0:
        print("Nenhum registro encontrado.")
        return

    for linha in dispositivosUSB:
        nomeDispositivo = linha[0]

        registros = buscarRegistrosComponente(idMaquina, nomeDispositivo)

        print()
        print("--", nomeDispositivo, "--")
        print("ID | Data/Hora | Conectada")

        for linhaRegistro in registros:
            idRegistro = linhaRegistro[0]
            dtHora = linhaRegistro[1]
            valorCaptura = linhaRegistro[2]

            print(idRegistro, "|", dtHora, "|", valorCaptura)


def visualizarDados():
    idMaquina = verificarMaquina()
    numeracaoMaquina = obterNumeracaoMaquina(idMaquina)

    while True:
        print()
        print("===== VISUALIZAR DADOS =====")
        print("Máquina número:", numeracaoMaquina)

        print("1 - Memória")
        print("2 - Disco")
        print("3 - Processador")
        print("4 - USB")
        print("5 - Voltar ao menu")

        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            visualizarMemoria(idMaquina)

        elif opcao == "2":
            visualizarDisco(idMaquina)

        elif opcao == "3":
            visualizarProcessador(idMaquina)

        elif opcao == "4":
            visualizarUSB(idMaquina)

        elif opcao == "5":
            break

        else:
            print("Opção inválida.")


# ==========================================================


def capturaAutomatica():
    print()
    print("===== CAPTURA AUTOMÁTICA =====")
    print("A captura vai rodar sozinha a cada 5 segundos.")
    print("Pressione qualquer tecla para parar.")

    while True:
        capturarDados()

        print()
        print("Próxima captura em 5 segundos... (pressione qualquer tecla para parar)")

        tempoInicio = time.time()
        parar = False

        while time.time() - tempoInicio < 5:
            if msvcrt.kbhit():
                msvcrt.getch()
                parar = True
                break
            time.sleep(0.1)

        if parar:
            break

    print()
    print("Captura automática encerrada.")


while True:
    print()
    print("==============================")
    print("         AQUASHIELD")
    print("==============================")

    print("Endereço MAC:", macFormatado)

    print()
    print("1 - Capturar dados")
    print("2 - Atualizar dados")
    print("3 - Deletar dados")
    print("4 - Captura automática")
    print("5 - Visualizar dados")
    print("6 - Sair")

    opcao = input("Escolha uma opção: ")

    if opcao == "1":
        capturarDados()

    elif opcao == "2":
        atualizarDados()

    elif opcao == "3":
        deletarDados()

    elif opcao == "4":
        capturaAutomatica()

    elif opcao == "5":
        visualizarDados()

    elif opcao == "6":
        print("Encerrando programa...")

        cursor.close()
        banco.close()

        break

    else:
        print("Opção inválida.")