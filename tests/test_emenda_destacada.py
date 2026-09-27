import pytest

from senado_pipeline.documento_processo import Escolha
from senado_pipeline.emenda_destacada import (
    BASES_VERIFICADAS,
    SEM_BASE,
    BaseEmenda,
    base_da_emenda,
    dispositivo,
)

TEXTO_DA_ETAPA = Escolha("RF_TEXTO", (9601918,))


def test_emenda_rejeitada_usa_o_texto_final_da_etapa():
    b = base_da_emenda("163100", "4", "R", TEXTO_DA_ETAPA)
    assert b == BaseEmenda("RF_TEXTO", (9601918,), "texto final da etapa; emenda rejeitada, o texto não a contém")


def test_emenda_aprovada_usa_a_base_verificada_e_tira_a_si_mesma_do_texto():
    b = base_da_emenda("160197", "139", "A", Escolha("COMPOSTO_INICIAL_MAIS_EMENDAS_DO_SENADO", (9459661, 9526122)))
    assert b == BASES_VERIFICADAS[("160197", "139")]
    # A emenda aprovada está dentro da redação final das Emendas do Senado; sem tirá-la, o delta
    # seria entre o texto e ele mesmo.
    assert b.remover_correspondente == "139"


def test_remover_correspondente_tira_so_o_bloco_da_emenda_pontuada():
    from senado_pipeline.emenda_destacada import remover_correspondente
    texto = ("A Comissão Diretora apresenta a redação final. "
             "EMENDA Nº 1 (Corresponde à Emenda nº 147 – Plen) Dê-se ao art. 1º ... "
             "EMENDA Nº 3 (Corresponde à Emenda nº 139 – Plen) Suprima-se o inciso IX ... "
             "EMENDA Nº 4 (Corresponde à Emenda nº 200 – Plen) Acrescente-se o art. 9º ...")
    limpo = remover_correspondente(texto, "139")
    assert "Suprima-se o inciso IX" not in limpo
    assert "Dê-se ao art. 1º" in limpo and "Acrescente-se o art. 9º" in limpo


def test_remover_correspondente_falha_alto_quando_o_mapeamento_nao_existe():
    from senado_pipeline.emenda_destacada import remover_correspondente
    with pytest.raises(ValueError):
        remover_correspondente("EMENDA Nº 1 (Corresponde à Emenda nº 999 – Plen) x", "139")


def test_emenda_aprovada_sem_base_verificada_fica_sem_nota():
    assert base_da_emenda("158930", "804", "A", TEXTO_DA_ETAPA) is None
    assert ("158930", "804") in SEM_BASE


def test_emenda_sem_numero_fica_sem_nota():
    assert base_da_emenda("166053", None, "A", TEXTO_DA_ETAPA) is None


def test_materia_com_base_verificada_mesmo_rejeitada_usa_a_verificada():
    # PL 4.932/2024: não há parecer nem redação final; o votado é o texto recebido da Câmara,
    # e o projeto foi à sanção sem voltar à Câmara.
    b = base_da_emenda("166801", "1", "R", None)
    assert b.ids_documento == (9876820,)
    assert "sanção" in b.evidencia


def test_rejeitada_sem_texto_da_etapa_e_sem_base_verificada_fica_sem_nota():
    assert base_da_emenda("999999", "1", "R", None) is None


def test_dispositivo_corta_na_justificacao():
    assert dispositivo("Art. 1º Fica revogado.\nJUSTIFICAÇÃO\nPorque sim.").strip() == "Art. 1º Fica revogado."
    assert dispositivo("Art. 1º Fica revogado.") == "Art. 1º Fica revogado."


def test_toda_emenda_sem_base_tem_motivo_escrito():
    assert set(SEM_BASE) == {("158930", "804"), ("166053", None)}
    assert all(len(m) > 20 for m in SEM_BASE.values())
