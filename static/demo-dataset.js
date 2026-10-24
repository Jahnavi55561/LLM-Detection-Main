/**
 * Predefined Claim Classification Dataset & Matcher
 * Internal classification dataset containing 15 supported and 15 contradicted claims.
 * Used to classify known claims directly in the Analyze & Verify workflow.
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
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 2,
            claim: "The Earth revolves around the Sun.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 3,
            claim: "IPv4 addresses are 32 bits long.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 4,
            claim: "The human heart has four chambers.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 5,
            claim: "The chemical formula of water is H2O.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 6,
            claim: "The Earth has one natural moon.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 7,
            claim: "Mars is known as the Red Planet.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 8,
            claim: "The Pacific Ocean is the largest ocean on Earth.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 9,
            claim: "Plants use sunlight for photosynthesis.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 10,
            claim: "DNA usually forms a double helix.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 11,
            claim: "Light travels faster than sound in air.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 12,
            claim: "Python is a high-level programming language.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 13,
            claim: "HTML is a markup language.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 14,
            claim: "HTTPS uses TLS to help encrypt data in transit.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },
        {
            id: 15,
            claim: "The capital of India is New Delhi.",
            status: "Supported",
            demo: true,
            explanation: "Verified against reference factual knowledge base."
        },

        // =========================================================================
        // 2. Incorrect / Contradicted Claims (15)
        // =========================================================================
        {
            id: 16,
            claim: "The Sun revolves around the Earth.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 17,
            claim: "IPv4 addresses are 128 bits long.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 18,
            claim: "The capital of Australia is Sydney.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 19,
            claim: "Humans normally have three lungs.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 20,
            claim: "The Earth is flat.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 21,
            claim: "The Moon produces its own visible light.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 22,
            claim: "The Sun is a planet.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 23,
            claim: "The Pacific Ocean is the smallest ocean on Earth.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 24,
            claim: "The chemical formula of water is CO2.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 25,
            claim: "Sound travels faster than light in air.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 26,
            claim: "HTML is a general-purpose programming language.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 27,
            claim: "HTTPS sends data in plaintext by default.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 28,
            claim: "The capital of India is Mumbai.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 29,
            claim: "Saturn has no rings.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        },
        {
            id: 30,
            claim: "Humans normally have 48 chromosomes in each body cell.",
            status: "Contradicted",
            demo: true,
            explanation: "Contradicted by reference factual knowledge base."
        }
    ];

    const ABBREVIATIONS = new Set([
        "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "vs", "etc", "e.g",
        "i.e", "u.s", "u.k", "ph.d", "gov", "gen", "rep", "sen", "sq", "km",
        "approx", "fig", "al", "inc", "ltd", "corp", "dept", "no", "univ",
        "est", "st", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
        "oct", "nov", "dec"
    ]);

    /**
     * Decomposes input text into sentences while protecting decimals,
     * initials, abbreviations, and list numbers.
     */
    function extractSentences(text) {
        text = String(text || "").trim();
        if (!text) return [];

        text = text.replace(/(\d+)\.(\d+)/g, "$1<DECIMAL>$2");
        text = text.replace(/\b([A-Z])\.\s+(?=[A-Z])/g, "$1<INITDOT> ");

        text = text.replace(/\b([a-zA-Z.]+)\./g, (match, prefix) => {
            if (ABBREVIATIONS.has(prefix.toLowerCase())) {
                return prefix + "<DOT>";
            }
            return match;
        });

        text = text.replace(/(^|\n)\s*(\d{1,3})\.\s+/g, "$1$2<NUMDOT> ");
        text = text.replace(/([.!?])\s+(\d{1,3})\.\s+/g, "$1 $2<NUMDOT> ");

        const rawSplits = text.split(/(?:[\r\n]+|(?<=[.!?])["']?\s+)/);
        const sentences = [];

        for (let s of rawSplits) {
            s = s.replace(/<DECIMAL>/g, ".")
                 .replace(/<INITDOT>/g, ".")
                 .replace(/<DOT>/g, ".")
                 .replace(/<NUMDOT>/g, ".");
            s = s.replace(/\s+/g, " ").trim();
            s = s.replace(/^(\d+[\.\)]\s*)+/, "").trim();
            if (s) {
                sentences.push(s);
            }
        }

        return sentences;
    }

    /**
     * Normalize claim key by lowercasing, collapsing whitespace,
     * stripping leading list bullets, and stripping trailing terminal punctuation.
     */
    function normalizeClaimKey(text) {
        return String(text || "")
            .trim()
            .toLowerCase()
            .replace(/^[0-9]+[\.\)]\s*/, "")
            .replace(/[\s\r\n]+/g, " ")
            .replace(/[.!?]+$/, "")
            .trim();
    }

    // Build fast lookup map for exact normalized matching
    const CLAIM_LOOKUP = new Map();
    DEMO_DATASET.forEach(item => {
        CLAIM_LOOKUP.set(normalizeClaimKey(item.claim), item);
    });

    /**
     * Exact normalized lookup for a claim against predefined dataset.
     */
    function matchPredefinedClaim(claimText) {
        const key = normalizeClaimKey(claimText);
        return CLAIM_LOOKUP.get(key) || null;
    }

    /**
     * Check if an array of sentences consists entirely of recognized predefined claims.
     * Returns an array of matched items if all match, or null if any claim is unknown.
     */
    function matchAllPredefinedClaims(sentences) {
        if (!Array.isArray(sentences) || sentences.length === 0) return null;

        const matches = [];
        for (const sentence of sentences) {
            const matched = matchPredefinedClaim(sentence);
            if (!matched) {
                return null; // Unknown claim found - fall back to live backend
            }
            matches.push({
                sentence: sentence,
                entry: matched
            });
        }
        return matches;
    }

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
        PREDEFINED_CLAIMS: DEMO_DATASET,
        getDemoCounts,
        getDemoClaimById,
        extractSentences,
        normalizeClaimKey,
        matchPredefinedClaim,
        matchAllPredefinedClaims
    };

    if (typeof module !== "undefined" && module.exports) {
        module.exports = exported;
    }

    if (typeof root !== "undefined") {
        root.DEMO_DATASET = DEMO_DATASET;
        root.PREDEFINED_CLAIMS = DEMO_DATASET;
        root.getDemoCounts = getDemoCounts;
        root.getDemoClaimById = getDemoClaimById;
        root.extractSentences = extractSentences;
        root.normalizeClaimKey = normalizeClaimKey;
        root.matchPredefinedClaim = matchPredefinedClaim;
        root.matchAllPredefinedClaims = matchAllPredefinedClaims;
    }
})(typeof globalThis !== "undefined" ? globalThis : this);
