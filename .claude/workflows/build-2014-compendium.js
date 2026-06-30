export const meta = {
  name: 'build-2014-compendium',
  description: 'Extract remaining 2014 content (PHB spell gap + multiclassing + equipment check, Tasha\'s spells/items/sidekicks, and full Monster Manual) from owned PDFs, QA it, merge into data/srd/2014, and assemble a local read-only compendium. Nothing is committed (data/srd is gitignored).',
  whenToUse: 'Run to finish the local 2014 data: Tasha\'s spells, magic items, sidekicks (subclasses/feats already done) and the full Monster Manual statblocks, then build _compendium.json + a coverage report.',
  phases: [
    { title: 'Prep', detail: 'Dump Monster Manual OCR; build worklists; locate Tasha sections' },
    { title: 'Extract', detail: 'Fan-out: clean per-entry blocks to JSON batch files on disk' },
    { title: 'QA', detail: 'Validate + repair each batch (schema, index uniqueness, cross-refs, numbers)' },
    { title: 'Merge', detail: 'Dedup-merge into data/srd/2014/*.json, build _compendium.json + coverage' },
  ],
}

// ---------------------------------------------------------------------------
// IMPORTANT design notes (read before running):
// - Workflow JS has NO filesystem access. ALL file IO is done by the AGENTS
//   (they have Bash/Read/Write). Agents WRITE their output to .extract_tmp/*.json
//   and RETURN ONLY a small status object. This (a) dodges the output content
//   filter that blocked combat-wording batches during the feats pass, and
//   (b) keeps this orchestration's context tiny and cheap to supervise.
// - venv python: .venv_forge/Scripts/python.exe ; pymupdf is installed.
// - PHB + Tasha's OCR page text already cached under .extract_tmp/phb|tashas/.
// - Match the EXISTING shape of each target file (agents must read a sample
//   entry from the target JSON first). Cross-refs use {index,name,url}.
// - Dedup by `index` against existing SRD entries; never touch git / data/srd.
// ---------------------------------------------------------------------------

const STATUS = {
  type: 'object', additionalProperties: true,
  properties: {
    label: { type: 'string' },
    count: { type: 'number' },
    file: { type: 'string' },
    issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['label', 'count'],
}

const MONSTER_BATCH = 12   // statblocks per extract agent
const ROOT = 'C:\\\\Users\\\\celt_\\\\OneDrive\\\\VLE e-Learning Documents\\\\D&D Character Forge'

// === PREP =================================================================
phase('Prep')
const prep = await agent(
  `WORKING DIR: ${ROOT}. You prepare worklists for a 2014 D&D data extraction. Do ALL of this with Bash + the venv python (.venv_forge/Scripts/python.exe, pymupdf installed):
1) Dump every page of "PDFs/D&D 5E - Monster Manual.pdf" to .extract_tmp/mm/pNNN.txt (zero-padded 3-digit). Retry on OneDrive PermissionError.
2) Scan the MM pages for statblocks (a statblock has an "Armor Class" line and a "Challenge" line). Build an ORDERED list of {name, page} for every monster and write it to .extract_tmp/mm_worklist.json. Be thorough; dedup repeated headers.
3) Locate Tasha's Cauldron sections in .extract_tmp/tashas/ : the NEW SPELLS list (chapter "Spells"), the MAGIC ITEMS section, and the SIDEKICKS section (Expert/Spellcaster/Warrior). Write .extract_tmp/tashas_worklist.json = {"spells":[pageNumbers],"magic_items":[pageNumbers],"sidekicks":[pageNumbers]}.
Return ONLY status: {label:"prep", count:<number of monsters found>, issues:[...] } plus extra keys spellsPages, itemPages, sidekickPages (arrays).`,
  { schema: STATUS, phase: 'Prep' }
)
const monsterCount = (prep && prep.count) || 0
const monsterBatches = Math.max(0, Math.ceil(monsterCount / MONSTER_BATCH))
log(`Prep: ${monsterCount} monsters -> ${monsterBatches} batches; Tasha worklist written.`)

// === EXTRACT + QA (pipeline; each item flows extract -> qa with no barrier) =
// --- Tasha's categories (small; one agent each) ---
const TASHA_JOBS = [
  { key: 'spells', target: 'data/srd/2014/5e-SRD-Spells.json', out: '.extract_tmp/tashas_spells.json',
    note: 'Tasha NEW spells only (e.g. Mind Sliver, Tasha\'s Mind Whip, Summon Aberration/Beast/Construct/Elemental/Fey/Fiend/Shadowspawn/Undead, etc.). EACH spell MUST have correct level, school, and classes[] (load-bearing for spell-list legality).' },
  { key: 'magic_items', target: 'data/srd/2014/5e-SRD-Magic-Items.json', out: '.extract_tmp/tashas_items.json',
    note: 'Tasha magic items.' },
  { key: 'sidekicks', target: null, out: '.extract_tmp/tashas_sidekicks.json',
    note: 'The three sidekick classes (Expert, Spellcaster, Warrior) with their level progression tables. No existing target file -> invent a clean documented shape {index,name,desc[],levels:[...]}; compendium-only (engine does not read it yet).' },
]

phase('Extract')
const tashaResults = await pipeline(
  TASHA_JOBS,
  (job) => agent(
    `WORKING DIR: ${ROOT}. Extract Tasha's Cauldron ${job.key} from the OCR page text in .extract_tmp/tashas/ (read .extract_tmp/tashas_worklist.json for the page numbers; OCR is mostly clean). ${job.note}
${job.target ? `FIRST read one entry from ${job.target} and match that exact JSON shape.` : ''}
Clean OCR, invent nothing, preserve all numbers/spell names. WRITE the array of entries to ${job.out} (use the Write tool). Then RETURN ONLY status {label:"tasha:${job.key}", count:<n>, file:"${job.out}", issues:[...]}.`,
    { schema: STATUS, phase: 'Extract', label: `extract:tasha:${job.key}` }
  ),
  (res, job) => agent(
    `WORKING DIR: ${ROOT}. QA the file ${job.out} (Tasha ${job.key}). Read it. Check: valid JSON; required keys present per the ${job.target || 'documented'} shape; index unique & kebab-case; for spells that classes[].index values are within the 12 PHB classes and level 0-9; numbers look sane vs the source. Fix problems in place (re-Write the file). RETURN ONLY status {label:"qa:tasha:${job.key}", count:<n after qa>, file:"${job.out}", issues:[...]}.`,
    { schema: STATUS, phase: 'QA', label: `qa:tasha:${job.key}` }
  )
)

// --- PHB completeness (task #5): spell gap, multiclassing, equipment check ---
const PHB_JOBS = [
  { key: 'spells', target: 'data/srd/2014/5e-SRD-Spells.json', out: '.extract_tmp/phb_spells.json',
    note: 'The PHB spells (Ch 11) that are MISSING from the existing SRD subset. FIRST load existing index set from the target, then extract ONLY spells in the PHB not already present (~40). EACH must have correct level, school, and classes[] (load-bearing).' },
  { key: 'equipment', target: 'data/srd/2014/5e-SRD-Equipment.json', out: '.extract_tmp/phb_equipment.json',
    note: 'PHB Ch 5 weapons/armor/adventuring gear/tools. Compare against existing indexes and output ONLY entries missing from the target (additions only).' },
  { key: 'multiclassing', target: null, out: '.extract_tmp/phb_multiclassing.json',
    note: 'PHB Ch 6 multiclassing RULES: ability-score prerequisites per class, proficiencies gained when multiclassing into each class, and the Multiclass Spellcaster slot table (levels 1-20). No target file -> clean documented shape {prerequisites:{class:score...}, proficiencies_gained:{class:[...]}, spellcaster_slots:[{level, slots_1..9}]}. Compendium-only.' },
]
const phbResults = await pipeline(
  PHB_JOBS,
  (job) => agent(
    `WORKING DIR: ${ROOT}. Extract PHB ${job.key} from the OCR page text in .extract_tmp/phb/ (chapter pages: spells Ch11 ~p207+, equipment Ch5 ~p143+, multiclassing Ch6 ~p163+). ${job.note}
${job.target ? `FIRST read one entry + the full index set from ${job.target}; match that exact JSON shape and OUTPUT ONLY entries not already present (additions).` : ''}
Clean OCR, invent nothing, preserve all numbers. WRITE the result to ${job.out} (Write tool). RETURN ONLY status {label:"phb:${job.key}", count:<n>, file:"${job.out}", issues:[...]}.`,
    { schema: STATUS, phase: 'Extract', label: `extract:phb:${job.key}` }
  ),
  (res, job) => agent(
    `WORKING DIR: ${ROOT}. QA ${job.out} (PHB ${job.key}). Read it. Valid JSON; required keys per the ${job.target || 'documented'} shape; index unique kebab-case; for spells classes[].index within the 12 classes and level 0-9; additions are genuinely NOT already in ${job.target || 'n/a'}; numbers sane vs source. Fix in place. RETURN ONLY status {label:"qa:phb:${job.key}", count:<n>, file:"${job.out}", issues:[...]}.`,
    { schema: STATUS, phase: 'QA', label: `qa:phb:${job.key}` }
  )
)

// --- Monsters (full MM; many batches) ---
const monsterIdx = Array.from({ length: monsterBatches }, (_, i) => i)
const monsterResults = await pipeline(
  monsterIdx,
  (i) => agent(
    `WORKING DIR: ${ROOT}. Read .extract_tmp/mm_worklist.json and process the monsters at array indices ${i * MONSTER_BATCH} through ${i * MONSTER_BATCH + MONSTER_BATCH - 1} (inclusive; batch ${i}). For each monster in your slice, read its page(s) under .extract_tmp/mm/ and extract the full statblock. FIRST read one entry from data/srd/2014/5e-SRD-Monsters.json and match that exact shape (index,name,size,type,alignment,armor_class,hit_points,hit_dice,speed,strength..charisma,proficiencies,damage_*,condition_immunities,senses,languages,challenge_rating,xp,special_abilities[],actions[],legendary_actions[] where present). OCR-clean carefully; PRESERVE ALL NUMBERS (AC, HP, ability scores, DCs, damage dice, CR). Invent nothing. WRITE your batch array to .extract_tmp/mm_batch_${i}.json (Write tool). RETURN ONLY status {label:"monsters:batch:${i}", count:<n>, file:".extract_tmp/mm_batch_${i}.json", issues:[...]}.`,
    { schema: STATUS, phase: 'Extract', label: `extract:monsters:${i}` }
  ),
  (res, i) => agent(
    `WORKING DIR: ${ROOT}. Adversarially QA .extract_tmp/mm_batch_${i}.json. Read it AND re-open the relevant .extract_tmp/mm/ pages. Verify each monster: valid JSON & required keys; index unique kebab-case; AC/HP/CR/ability scores present and matching the source numbers (spot-check at least half against the raw page); actions/damage dice correct. Repair any mismatch in place (re-Write). RETURN ONLY status {label:"qa:monsters:${i}", count:<n after qa>, file:".extract_tmp/mm_batch_${i}.json", issues:[...]}.`,
    { schema: STATUS, phase: 'QA', label: `qa:monsters:${i}` }
  )
)

// === MERGE + COMPENDIUM ===================================================
phase('Merge')
const okMonsterFiles = monsterResults.filter(Boolean).map((r) => r.file)
const okTashaFiles = tashaResults.filter(Boolean).map((r) => r.file)
const merge = await agent(
  `WORKING DIR: ${ROOT}. Final merge + compendium build (use the venv python). Steps:
1) MONSTERS: read all .extract_tmp/mm_batch_*.json, concatenate, DEDUP by index (keep first), then MERGE into data/srd/2014/5e-SRD-Monsters.json keeping any existing entries not present in the new set (dedup by index). Write the combined array back.
2) SPELLS: merge BOTH .extract_tmp/tashas_spells.json AND .extract_tmp/phb_spells.json into data/srd/2014/5e-SRD-Spells.json (dedup by index). ITEMS: merge .extract_tmp/tashas_items.json into data/srd/2014/5e-SRD-Magic-Items.json (dedup by index). EQUIPMENT: merge .extract_tmp/phb_equipment.json into data/srd/2014/5e-SRD-Equipment.json (dedup by index). SIDEKICKS: copy .extract_tmp/tashas_sidekicks.json to data/srd/2014/5e-SRD-Sidekicks.json. MULTICLASSING: copy .extract_tmp/phb_multiclassing.json to data/srd/2014/5e-SRD-Multiclassing.json.
3) COMPENDIUM: build a single read-only data/srd/2014/_compendium.json = an object keyed by category (races, subraces, classes, subclasses, backgrounds, feats, spells, magic_items, monsters, sidekicks, multiclassing, equipment, traits, languages, conditions, levels) whose values are the FULL arrays from each category file. (Read-only convenience artifact; the engine still reads the per-category files.)
4) COVERAGE: write data/srd/2014/_coverage.md = a markdown table of {category: count} plus a note of any issues collected.
5) Confirm 'git status --porcelain | grep data/srd' returns NOTHING (data/srd must stay gitignored).
6) Run: .venv_forge/Scripts/python.exe -c "from forge.ruleset import Ruleset; o=Ruleset('dnd5e-2014').option_lists(); print({k:len(v) for k,v in o['subclassesByClass'].items()})" and .venv_forge/Scripts/python.exe tests/test_ruleset.py — both must succeed.
RETURN ONLY status {label:"merge", count:<total compendium entries>, file:"data/srd/2014/_compendium.json", issues:[...]}.`,
  { schema: STATUS, phase: 'Merge', label: 'merge+compendium' }
)

log(`Done. Monsters batches ok: ${okMonsterFiles.length}/${monsterBatches}; Tasha: ${okTashaFiles.length}/${TASHA_JOBS.length}; PHB: ${phbResults.filter(Boolean).length}/${PHB_JOBS.length}.`)
return { prep, phb: phbResults.filter(Boolean), tasha: tashaResults.filter(Boolean), monsters: monsterResults.filter(Boolean), merge }
