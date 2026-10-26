if not dentro.empty
                    else None
                )

                resultados.append({
                    "Tipo": tipo,
                    "Tipo_alvo": tipo_alvo,
                    "Prazo_pregoes": prazo,
                    "Operacoes_avaliaveis": avaliaveis,
                    "Atingiu_dentro": len(dentro),
                    "Atingiu_depois": len(depois),
                    "Nao_atingiu_no_historico": len(nao_atingiu),
                    "Inconclusivos": len(inconclusivos),
                    "Sem_alvo_historico": len(sem_alvo),
                    "Taxa_atingimento_pct": (
                        round(taxa, 2)
                        if taxa is not None
                        else None
                    ),
                    "Mediana_pregoes_ate_alvo": mediana_tempo
                })

    return pd.DataFrame(resultados)



def testar():

    ativo = "PETR4"

    print("=" * 80)
    print("AUDITORIA DA ESTRATEGIA INTRADAY")
    print("=" * 80)

    dados = coletar_candles_intraday(ativo)
    dados_diarios = coletar_candles_diarios(ativo)

    if dados.empty:
        print("Nenhum candle foi coletado.")
        return

    print(f"\nAtivo: {ativo}")
    print(f"Total de candles: {len(dados)}")
    print(f"Primeiro candle: {dados['Data'].iloc[0]}")
    print(f"Ultimo candle: {dados['Data'].iloc[-1]}")

    dados = gerar_sinais_intraday(dados)
    auditoria = auditar_sinais(dados)
    alvos = avaliar_alvos_por_pregoes(dados, auditoria, dados_diarios)
    resumo_alvos = resumir_alvos_por_pregoes(alvos)

    if auditoria.empty:
        print("\nNenhuma rejeicao encontrada.")
    else:
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 240)
        pd.set_option("display.max_colwidth", 25)

        print("\n" + "=" * 80)
        print("DETALHAMENTO DAS REJEICOES")
        print("=" * 80)

        print(
            auditoria.round(3).to_string(index=False)
        )

        print("\n" + "=" * 80)
        print("RESUMO DA AUDITORIA")
        print("=" * 80)

        print(f"Rejeicoes encontradas: {len(auditoria)}")
        print(
            "Compras:",
            len(auditoria[auditoria["Tipo"] == "COMPRA"])
        )
        print(
            "Vendas:",
            len(auditoria[auditoria["Tipo"] == "VENDA"])
        )
        print(
            "Confirmadas:",
            len(auditoria[auditoria["Status"] == "CONFIRMADA"])
        )
        print(
            "Sem confirmacao:",
            len(auditoria[auditoria["Status"] == "SEM CONFIRMAÇÃO"])
        )

        print("\nSinais confirmados registrados pelo motor:")
        print(dados["Sinal"].value_counts().to_string())
        
        
        print("\n" + "=" * 80)
        print("AUDITORIA DOS ALVOS POR PRAZO EM PREGOES")
        print("=" * 80)

        if alvos.empty:
            print("Nenhuma entrada confirmada para avaliar.")
        else:
            print(alvos.to_string(index=False))

            print("\n" + "=" * 80)
            print("RESUMO ESTATISTICO DOS ALVOS")
            print("=" * 80)

            if resumo_alvos.empty:
                print("Nenhum resultado disponível para resumir.")
            else:
                print(resumo_alvos.to_string(index=False))


    print("\nAuditoria concluida!")


if __name__ == "__main__":
    testar()
