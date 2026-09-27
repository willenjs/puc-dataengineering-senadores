from pathlib import Path

from senado_pipeline.extrator_texto import MARCADOR, higienizar, vazamentos

TEXTOS = Path(__file__).parent / "fixtures" / "v3" / "textos"
# Nomes que aparecem nas três fixtures, grafados como em dim_senador.nome_senador.
NOMES = [
    "Veneziano Vital do Rêgo", "Weverton", "Dr. Hiran", "Rodrigo Cunha", "Oriovisto Guimarães",
    "Esperidião Amin", "Luiz do Carmo", "Antonio Anastasia", "Tasso Jereissati",
]


def _ler(nome):
    return (TEXTOS / f"{nome}.txt").read_text(encoding="utf-8")


def test_higienizar_remove_bloco_de_assinatura_da_comissao_diretora():
    limpo = higienizar(_ler("9407624"), NOMES)
    assert vazamentos(limpo, NOMES) == []
    assert "VENEZIANO" not in limpo and "WEVERTON" not in limpo and "HIRAN" not in limpo
    assert "Efraim" not in limpo  # "do Deputado Efraim Filho", deputado fora de dim_senador
    assert "Art. 11. Esta Lei Complementar entra em vigor" in limpo  # o conteúdo fica


def test_higienizar_remove_chancela_e_assinatura_de_deputado_que_nao_esta_na_lista():
    limpo = higienizar(_ler("9880336"), NOMES)
    assert vazamentos(limpo, NOMES) == []
    assert "LIRA" not in limpo.upper()
    assert "infoleg" not in limpo and "2844988" not in limpo
    assert "O CONGRESSO NACIONAL decreta" in limpo


def test_higienizar_remove_assinatura_eletronica_e_mencoes_no_corpo():
    limpo = higienizar(_ler("9405161"), NOMES)
    assert vazamentos(limpo, NOMES) == []
    assert "Oriovisto" not in limpo and "ORIOVISTO" not in limpo
    assert "Anastasia" not in limpo and "Jereissati" not in limpo  # "os Senadores Antônio Anastasia e Tasso Jereissati"
    assert "autenticadoc" not in limpo


def test_nome_da_lista_casa_sem_acento_e_sem_caixa():
    assert MARCADOR in higienizar("apoio do senador antônio anastasia ao texto", ["Antonio Anastasia"])


def test_vazamentos_acusa_nome_url_e_tratamento_abreviado():
    achados = vazamentos("Assinado por Sen. Fulano, ver https://x.y/z; Weverton votou", ["Weverton"])
    assert any("Weverton" in a for a in achados)
    assert any("http" in a for a in achados)
    assert any("Sen." in a for a in achados)


def test_higienizar_nao_toca_em_senado_federal_nem_em_senadores_minusculo():
    t = "O Senado Federal aprovou. Os senadores discutiram. Senhoras Senadoras e Senhores Senadores, obrigado."
    assert higienizar(t, NOMES) == t


def test_tratamento_nao_atravessa_linha_nem_fim_de_frase():
    t = "do Deputado Efraim Filho. \n \nA Comissão Diretora, em Plenário, apresenta\nDeputado Efraim Filho. \n \nInstitui o Estatuto"
    limpo = higienizar(t, [])
    assert "A Comissão Diretora, em Plenário" in limpo
    assert "Institui o Estatuto" in limpo
    assert "Efraim" not in limpo


def test_tratamento_preserva_o_cargo_na_linha_seguinte():
    limpo = higienizar("Senador RODRIGO PACHECO\nPresidente do Senado Federal", [])
    assert limpo == f"{MARCADOR}\nPresidente do Senado Federal"


def test_tratamento_aceita_abreviatura_de_titulo():
    assert higienizar("o Senador Dr. Hiran votou", []) == f"o {MARCADOR} votou"
