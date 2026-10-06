ALTER TABLE tradedesk_trade_results
    DROP CONSTRAINT tradedesk_trade_results_evidence_version_check;

ALTER TABLE tradedesk_trade_results
    ADD CONSTRAINT tradedesk_trade_results_evidence_version_check
        CHECK (evidence_version IN ('1.1-legacy', '1.2', '1.2-core'));
