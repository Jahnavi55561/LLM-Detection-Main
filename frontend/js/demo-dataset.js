/**
 * Deterministic Claim Verification Demo Dataset
 * Client-requested demonstration dataset containing 15 supported and 15 contradicted claims.
 * Used exclusively for explicit frontend demo execution.
 */
(function(root) {
    "use strict";

    const DEMO_DATASET = [
        // =========================================================================
        // 1. Supported Claims (15)
        // =========================================================================
        {
            id: 1,
            claim: "The capital of Australia is Canberra.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 2,
            claim: "The Earth revolves around the Sun.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 3,
            claim: "IPv4 addresses are 32 bits long.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 4,
            claim: "The human heart has four chambers.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 5,
            claim: "The chemical formula of water is H2O.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 6,
            claim: "The Earth has one natural moon.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 7,
            claim: "Mars is known as the Red Planet.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 8,
            claim: "The Pacific Ocean is the largest ocean on Earth.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 9,
            claim: "Plants use sunlight for photosynthesis.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 10,
            claim: "DNA usually forms a double helix.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 11,
            claim: "Light travels faster than sound in air.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 12,
            claim: "Python is a high-level programming language.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 13,
            claim: "HTML is a markup language.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 14,
            claim: "HTTPS uses TLS to help encrypt data in transit.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 15,
            claim: "The capital of India is New Delhi.",
            status: "Supported",
            demo: true,
            explanation: "Predefined demonstration result (expected: Supported). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },

        // =========================================================================
        // 2. Incorrect / Contradicted Claims (15)
        // =========================================================================
        {
            id: 16,
            claim: "The Sun revolves around the Earth.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 17,
            claim: "IPv4 addresses are 128 bits long.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 18,
            claim: "The capital of Australia is Sydney.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 19,
            claim: "Humans normally have three lungs.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 20,
            claim: "The Earth is flat.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 21,
            claim: "The Moon produces its own visible light.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 22,
            claim: "The Sun is a planet.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 23,
            claim: "The Pacific Ocean is the smallest ocean on Earth.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 24,
            claim: "The chemical formula of water is CO2.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 25,
            claim: "Sound travels faster than light in air.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 26,
            claim: "HTML is a general-purpose programming language.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 27,
            claim: "HTTPS sends data in plaintext by default.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 28,
            claim: "The capital of India is Mumbai.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 29,
            claim: "Saturn has no rings.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        },
        {
            id: 30,
            claim: "Humans normally have 48 chromosomes in each body cell.",
            status: "Contradicted",
            demo: true,
            explanation: "Predefined demonstration result (expected: Contradicted). Live evidence retrieval was not performed.",
            evidence: "Predefined demo result — live evidence retrieval was not performed."
        }
    ];

    /**
     * Dynamically compute counts directly from the dataset.
     */
    function getDemoCounts() {
        let supported = 0;
        let contradicted = 0;
        let unverified = 0;

        for (const item of DEMO_DATASET) {
            if (item.status === "Supported") supported++;
            else if (item.status === "Contradicted") contradicted++;
            else unverified++;
        }

        return {
            total: DEMO_DATASET.length,
            supported: supported,
            contradicted: contradicted,
            unverified: unverified,
            counts: {
                Supported: supported,
                Contradicted: contradicted,
                Unverified: unverified
            }
        };
    }

    function getDemoClaimById(id) {
        const numId = Number(id);
        return DEMO_DATASET.find(item => item.id === numId) || null;
    }

    const exported = {
        DEMO_DATASET,
        getDemoCounts,
        getDemoClaimById
    };

    if (typeof module !== "undefined" && module.exports) {
        module.exports = exported;
    }

    if (typeof root !== "undefined") {
        root.DEMO_DATASET = DEMO_DATASET;
        root.getDemoCounts = getDemoCounts;
        root.getDemoClaimById = getDemoClaimById;
    }
})(typeof globalThis !== "undefined" ? globalThis : this);
