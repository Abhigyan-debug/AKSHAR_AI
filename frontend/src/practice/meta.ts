// Practice games (see docs/practice.md). Each game targets one error pattern from the report.
// Text for adults is Hindi: parents in Hindi-medium schools are the main co-players.

export type GameId = 'matra' | 'breath' | 'twins' | 'builder' | 'mirror' | 'readalong'

export interface GameMeta {
  id: GameId
  title: string
  lang: 'hi' | 'en'
  childLine: string // what the child is asked to do
  practises: string // for the adult: what this trains
  adultTip: string // how to sit alongside (published evidence: games work far better with an adult)
  followUp: string // one thing to do away from the phone
}

export const GAMES: Record<GameId, GameMeta> = {
  matra: {
    id: 'matra',
    title: 'मात्रा पहचानो',
    lang: 'hi',
    childLine: 'सुनो और सही शब्द चुनो',
    practises: 'छोटी-बड़ी मात्रा का फ़र्क (जैसे मिल और मील)',
    adultTip: 'बच्चे के साथ बैठें। हर शब्द के बाद बच्चे से उसे ज़ोर से दोहराने को कहें।',
    followUp: 'आज दो ऐसे शब्द चुनें जिनमें छोटी इ (ि) और बड़ी ई (ी) हो, और बच्चे को बोलकर लिखवाएँ।',
  },
  breath: {
    id: 'breath',
    title: 'हवा वाले अक्षर',
    lang: 'hi',
    childLine: 'क या ख? ध्यान से सुनो',
    practises: 'हवा वाली और बिना हवा वाली आवाज़ें (जैसे पल और फल)',
    adultTip: 'मुँह के सामने हथेली रखकर "ख" बोलें, हवा लगेगी; "क" में कम हवा लगती है। बच्चे से भी ऐसा करवाएँ।',
    followUp: 'घर की चीज़ों के नाम में ख, घ, छ, ध, फ, भ ढूँढें और हथेली वाला खेल खेलें।',
  },
  twins: {
    id: 'twins',
    title: 'जुड़वाँ अक्षर',
    lang: 'hi',
    childLine: 'ऊपर वाला अक्षर नीचे ढूँढो',
    practises: 'एक जैसे दिखने वाले अक्षर (जैसे ब और व, भ और म)',
    adultTip: 'ढूँढने से पहले बच्चे से अक्षर को उँगली से हवा में बनाने को कहें।',
    followUp: 'अख़बार के एक छोटे हिस्से में एक अक्षर, जैसे ब, पर गोला लगवाएँ।',
  },
  builder: {
    id: 'builder',
    title: 'शब्द बनाओ',
    lang: 'hi',
    childLine: 'सुनो और टुकड़े जोड़कर शब्द बनाओ',
    practises: 'शब्द को ध्यान से पढ़ना, अंदाज़ा नहीं लगाना',
    adultTip: 'पहले शब्द को धीरे-धीरे टुकड़ों में बोलें, जैसे बा... द... ल, फिर बच्चे को जोड़ने दें।',
    followUp: 'रोज़ दो नए शब्द ताली बजाकर टुकड़ों में बोलें, जैसे म-ट-र।',
  },
  mirror: {
    id: 'mirror',
    title: 'b, d, p, q',
    lang: 'en',
    childLine: 'Listen and pick the first letter',
    practises: 'अंग्रेज़ी के उल्टे दिखने वाले अक्षर b, d, p, q',
    adultTip: 'दोनों हाथों की मुट्ठी बनाकर अंगूठे ऊपर करें: बच्चे की ओर से बायाँ हाथ b जैसा और दायाँ हाथ d जैसा दिखता है।',
    followUp: 'b और d वाले शब्द पढ़ते समय बच्चे को हाथ वाला तरीका याद दिलाएँ।',
  },
  readalong: {
    id: 'readalong',
    title: 'साथ-साथ पढ़ो',
    lang: 'hi',
    childLine: 'सुनो, साथ पढ़ो, फिर खुद पढ़ो',
    practises: 'धाराप्रवाह पढ़ना: एक ही कहानी तीन बार',
    adultTip: 'पहली बार साथ सुनें। दूसरी बार उँगली रखकर साथ पढ़ें। तीसरी बार बच्चे को अकेले पढ़ने दें और तारीफ़ करें।',
    followUp: 'रोज़ एक छोटी कहानी तीन बार पढ़ें: पहले आप, फिर साथ में, फिर बच्चा।',
  },
}

export const GAME_ORDER: GameId[] = ['matra', 'breath', 'twins', 'builder', 'mirror', 'readalong']

export interface PracticeContent {
  version: number
  games: {
    matra: { lang: 'hi'; pairs: [string, string][] }
    breath: { lang: 'hi'; pairs: [string, string][] }
    twins: { lang: 'hi'; pairs: [string, string][] }
    builder: { lang: 'hi'; words: { word: string; tiles: string[]; distractors: string[]; is_nonword: boolean }[] }
    mirror: { lang: 'en'; words: string[] }
    readalong: { stories: { id: string; lang: 'hi' | 'en'; title: string; lines: string[] }[] }
  }
}
