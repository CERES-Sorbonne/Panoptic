// Benchmark en JavaScript (Node.js ou navigateur console)
// Lancez via Node: node <nom_du_fichier>.js

const NUM_ELEMENTS = 100000; 

// --- 1. FONCTIONS UTILITAIRES ET PRÉPARATION DES DONNÉES ---

function generateRandomString(length = 5) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

function setupData() {
    console.log(`\n--- 1. PRÉPARATION DES DONNÉES JAVASCRIPT (${NUM_ELEMENTS} éléments) ---`);
    const data = {
        elements: [],
        prop1: new Map(), // Couleurs (faible cardinalité)
        prop2: new Map(), // Catégories (moyenne cardinalité)
        prop3: new Map(), // Rating (faible cardinalité, 1-10)
        wide_elements: [] // Schéma dénormalisé pour comparaison
    };

    const p1_choices = ['RED', 'BLUE', 'GREEN', 'YELLOW', 'BLACK'];
    const p2_choices = Array.from({ length: 50 }, () => generateRandomString());

    const startSetup = performance.now();

    for (let i = 0; i < NUM_ELEMENTS; i++) {
        const p1_val = p1_choices[Math.floor(Math.random() * p1_choices.length)];
        const p2_val = p2_choices[Math.floor(Math.random() * p2_choices.length)];
        const p3_val = Math.floor(Math.random() * 10) + 1; // Rating 1-10

        // 1. Schéma Normalisé (Simule les tables séparées)
        data.prop1.set(i, p1_val);
        data.prop2.set(i, p2_val);
        data.prop3.set(i, p3_val);

        // 2. Schéma Dénormalisé (Wide Table)
        data.wide_elements.push({
            id: i,
            p1: p1_val,
            p2: p2_val,
            p3: p3_val
        });
    }

    const endSetup = performance.now();
    console.log(`  Données Prêtes. Temps de génération : ${(endSetup - startSetup).toFixed(2)} ms\n`);
    return data;
}


// --- 2. BENCHMARK : FILTRAGE MULTI-CRITÈRES ---

function benchmarkFiltering(data) {
    console.log("--- 2. BENCHMARK: FILTRAGE MULTI-CRITÈRES ---");
    console.log("Goal: Trouver les éléments où Prop1='RED' ET Prop3 > 5");
    
    const TARGET_P1 = 'RED';
    const TARGET_P3 = 5;
    let resultsCount;

    // --- A. Normalisé (Simule le JOIN en JS) ---
    // C'est l'équivalent JS de la requête SQL la plus coûteuse.
    console.time("JS Normalisé (Filter + Join)");
    const resultsNorm = [];
    for (let i = 0; i < NUM_ELEMENTS; i++) {
        const p1_val = data.prop1.get(i);
        const p3_val = data.prop3.get(i);
        
        // Simule le WHERE
        if (p1_val === TARGET_P1 && p3_val > TARGET_P3) {
            resultsNorm.push(i);
        }
    }
    console.timeEnd("JS Normalisé (Filter + Join)");
    resultsCount = resultsNorm.length;

    // --- B. Dénormalisé (Le plus rapide en JS) ---
    // Simule la lecture de votre table Wide optimisée.
    console.time("JS Dénormalisé (Filter Only)");
    const resultsWide = data.wide_elements.filter(e => e.p1 === TARGET_P1 && e.p3 > TARGET_P3);
    console.timeEnd("JS Dénormalisé (Filter Only)");

    console.log(`  Rows trouvées : ${resultsCount}\n`);
}


// --- 3. BENCHMARK : GROUPAGE MULTI-PROPRIÉTÉS ---

function benchmarkMultiGrouping(data) {
    console.log("--- 3. BENCHMARK: MULTI-GROUPAGE (Prop1, Prop2, Prop3) ---");
    let groupsCount;

    // --- A. Normalisé (Simule le JOIN + GROUP BY en JS) ---
    console.time("JS Normalisé (Join + Group)");
    const groupsNorm = new Map();
    for (let i = 0; i < NUM_ELEMENTS; i++) {
        // Simule le JOIN
        const key = `${data.prop1.get(i)}|${data.prop2.get(i)}|${data.prop3.get(i)}`;
        
        // Simule le GROUP BY et le COUNT
        groupsNorm.set(key, (groupsNorm.get(key) || 0) + 1);
    }
    console.timeEnd("JS Normalisé (Join + Group)");
    groupsCount = groupsNorm.size;

    // --- B. Dénormalisé (Le plus rapide en JS) ---
    // Simule le GROUP BY sur la table Wide (la meilleure performance possible en JS)
    console.time("JS Dénormalisé (Group Only)");
    const groupsWide = new Map();
    data.wide_elements.forEach(e => {
        const key = `${e.p1}|${e.p2}|${e.p3}`;
        groupsWide.set(key, (groupsWide.get(key) || 0) + 1);
    });
    console.timeEnd("JS Dénormalisé (Group Only)");

    console.log(`  Groupes uniques trouvés : ${groupsCount}\n`);
}

// --- EXECUTION PRINCIPALE ---
const appData = setupData();
benchmarkFiltering(appData);
benchmarkMultiGrouping(appData);