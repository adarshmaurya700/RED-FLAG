def marketplace_notice(case: dict) -> dict:
    return {
        "title": "Marketplace seller investigation and takedown request",
        "requested_action": "Investigate the identified listing and seller; suspend affected listings if the marketplace confirms policy violations.",
        "marketplaces": ["Amazon.in", "Flipkart", "HealthKart", "1mg"],
        "identified_sellers": case.get("sellers", []),
        "affected_products": case.get("products", []),
        "indicators": case.get("attribution_reasons", {}).get("counterfeit", []),
        "scope": "Named seller/listing only; brand-wide action requires separate corroboration.",
        "evidence_status": "Reported authenticity concerns and lab allegations require verification.",
    }


def authentication_advisory(case: dict) -> dict:
    return {
        "title": "Consumer product authentication advisory",
        "product": case["product_name"],
        "steps": [
            "Check the inner seal and manufacturer hologram before use.",
            "Use the manufacturer's official website to verify the QR/barcode destination.",
            "Record the batch and seller invoice. Avoid consuming a product with a broken seal.",
            "Contact the authorized brand channel about suspected counterfeits.",
        ],
        "qualification": "Dissolution and packaging appearance alone cannot establish counterfeit status.",
    }


def laboratory_request(case: dict) -> dict:
    return {
        "title": "Independent laboratory audit request",
        "products": case.get("products", []),
        "tests_requested": [
            "Validated NMR and isotope testing for the alleged honey syrup adulteration",
            "Protein identity, content and contaminant testing for the implicated supplement",
        ],
        "requirements": [
            "Accredited laboratory",
            "Documented chain of custody",
            "Batch and seller identity",
            "Report method, uncertainty and limits of detection",
        ],
        "status": "Draft request; no test has been commissioned.",
    }


def dark_store_alert(case: dict) -> dict:
    return {
        "title": "Hyperlocal stock quarantine and cold-chain audit advisory",
        "nodes": case.get("dark_store_nodes", []),
        "product": case["product_name"],
        "requested_actions": [
            "Identify and segregate implicated stock at each named node.",
            "Conduct FEFO and expiry checks, pest inspection and temperature-log review.",
            "Compare affected lots against unaffected D2C and supermarket channels.",
            "Record inspection findings before expanding geographic scope.",
        ],
        "scope": "Separate local nodes; no inferred radius from a PIN prefix and no automatic national recall.",
        "unaffected_channel_observation": case.get(
            "unaffected_channels", "Not established"
        ),
    }
