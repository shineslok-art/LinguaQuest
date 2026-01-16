import asyncio
import json
import time
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from dotenv import load_dotenv
import os
import google.generativeai as genai

# Constants

load_dotenv()
GEMINI: str = os.getenv("API_KEY")
TOKEN: str = os.getenv("TOKEN")
LANGUAGE_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
LANGUAGES = {
    "ru": "Russian",
    "kz": "Kazakh",
    "en": "English"
}

TRANSLATIONS = {
    "select_lang": {
        "en": "Please select your native language",
        "kz": "Тілді таңдаңыз",
        "ru": "Выберите родной язык"
    },
    "lang_set": {
        "en": "Your native language is set to {lang}.",
        "kz": "Сіздің ана тіліңіз {lang} деп орнатылды.",
        "ru": "Ваш родной язык установлен на {lang}."
    },
    "no_lang": {
        "en": "Please select your native language first.",
        "kz": "Алдымен ана тіліңізді таңдаңыз.",
        "ru": "Сначала выберите родной язык."
    },
    "completed": {
        "en": "You completed all missions! Congratulations!",
        "kz": "Барлық миссияларды аяқтадыңыз! Құттықтаймыз!",
        "ru": "Вы выполнили все задания! Поздравляем!"
    },
    "start_mission": {
        "en": "Mission {mission} started.",
        "kz": "Миссия {mission} басталды.",
        "ru": "Миссия {mission} началась."
    },
    "xp_gain": {
        "en": "+{xp} XP! 🎉",
        "kz": "+{xp} XP! 🎉",
        "ru": "+{xp} XP! 🎉"
    },
    "use_english_only": {
        "en": "Remember: Answer using ONLY English!",
        "kz": "Есте сақтаңыз: Тек ғана ағылшын тілінде жауап беріңіз!",
        "ru": "Помните: Отвечайте ТОЛЬКО на английском!"
    },
    "choose_option": {
        "en": "Choose an option:",
        "kz": "Опцияны таңдаңыз:",
        "ru": "Выберите вариант:"
    },
    "incorrect_try_again": {
        "en": "Incorrect. Try again.",
        "kz": "Қате. Қайтадан көріңіз.",
        "ru": "Неправильно. Попробуйте еще раз."
    },
    "api_limit_error": {
        "en": "API limit exceeded. Please try again in a moment.",
        "kz": "API лимити асты. Бір сәтте қайтадан көріңіз.",
        "ru": "Лимит API превышен. Попробуйте через время."
    },
    "answer_incorrect": {
        "en": "Your answer is not correct. Please try again.",
        "kz": "Сіздің жауабыңыз дұрыс емес. Қайтадан көріңіз.",
        "ru": "Ваш ответ неправильный. Попробуйте еще раз."
    },
    "correct_answer": {
        "en": "Correct! ✓",
        "kz": "Дұрыс! ✓",
        "ru": "Правильно! ✓"
    },
    "wrong_input_type": {
        "en": "This stage requires a different input type.",
        "kz": "Бұл кезең басқа енгіз түрі қажет.",
        "ru": "На этом этапе требуется другой тип ввода."
    },
    "use_help": {
        "en": "Use /help to see available commands",
        "kz": "/help қолданыңыз қолжетімді командаларды көру үшін",
        "ru": "Используйте /help для просмотра доступных команд"
    },
    "help_message": {
        "en": "Available commands:\n/quest - Start a mission\n/progress - Check your level and XP\n/help - Show this message",
        "kz": "Қолжетімді командалар:\n/quest - Миссияны бастау\n/progress - Деңгейіңіз бен XP тексеріңіз\n/help - Бұл хабарламаны көрсету",
        "ru": "Доступные команды:\n/quest - Начать миссию\n/progress - Проверить уровень и XP\n/help - Показать это сообщение"
    },
    "progress_message": {
        "en": "📊 Your Progress:\nLevel: {level}\nTotal XP: {xp}\nXP to next level: {xp_to_next}",
        "kz": "📊 Сіздің ілгерілеуіңіз:\nДеңгей: {level}\nБарлық XP: {xp}\nСледующий деңгейге XP: {xp_to_next}",
        "ru": "📊 Ваш прогресс:\nУровень: {level}\nОбщее XP: {xp}\nXP до следующего уровня: {xp_to_next}"
    },
    "completed_all": {
        "en": "🎉 You completed all missions! Congratulations!\nUse /progress to check your level",
        "kz": "🎉 Барлық миссияларды аяқтадыңыз! Құттықтаймыз!\n/progress қолданыңыз деңгейіңізді тексеру үшін",
        "ru": "🎉 Вы выполнили все задания! Поздравляем!\nИспользуйте /progress для проверки уровня"
    }
}

# Initialize

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

genai.configure(api_key=GEMINI)

# Memory

users = {}
last_api_call = {}
translation_cache = {}  # Cache for translations

def get_user(user_id: int):
    if user_id not in users:
        users[user_id] = {
            "native_lang": None,
            "native_lang_code": None,
            "learning_lang": "English",
            "mission": 0,
            "stage": 1,
            "xp": 0,
            "level": "A1"
            }
    return users[user_id]

def wait_for_api_limit():
    """Rate limiting to avoid API quota exceeded - increased delay"""
    user_id = "global"
    if user_id in last_api_call:
        elapsed = time.time() - last_api_call[user_id]
        min_delay = 3
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
    last_api_call[user_id] = time.time()

# Load mission from JSON

mission_1 = {}
with open("missions/mission_1.json", "r", encoding="utf-8") as f:
    mission_1 = json.load(f)

# Prompt

PROMPT = """
You are an English tutor inside a language learning game.

Mission goal: {goal}
Student level: {level}

Allowed sentence patterns:
{allowed_patterns}

Required elements:
{required_elements}

Examples of correct answers:
{examples}

Rules:
- User explanations must be in this language: {native_lang}
- The user must answer Only in {learning_lang}
- Be strict but fair
- Accept small variations
- Return Only valid JSON
- No extra text
- Output only the JSON object, no code blocks or markdown
- Provide detailed, educational feedback that explains the mistake, why it's incorrect, and how to correct it, including examples or tips to help learn the language

JSON format:
{{
    "correct": true/false,
    "intent_match": true/false,
    "grammar_ok": true/false,
    "errors": [],
    "feedback": "detailed explanation in native language explaining the mistake and teaching the language",
}}

User input: "{user_text}"
"""

# llm

def llm_check(user_text: str, stage: dict, explain_lang: str, native_lang_code: str) -> dict:
    wait_for_api_limit()
    
    prompt = PROMPT.format(
        learning_lang=stage.get("learning_lang", "English"),
        goal=stage.get("goal", ""),
        level=stage.get("level", "A1"),
        
        allowed_patterns="\n".join(stage.get("allowed_patterns", [])),
        required_elements=",".join(stage.get("required_elements", [])),
        
        examples="\n".join(stage.get("examples", [])),
        native_lang=explain_lang,
        user_text=user_text
    )
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(prompt)
    
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    
    try:
        return json.loads(text)
    except:
        return {
            "correct": False,
            "intent_match": False,
            "grammar_ok": False,
            "errors": ["llm_error"],
            "feedback": TRANSLATIONS["answer_incorrect"][native_lang_code]
        }

# Translate

def translate_text(text: str, target_lang_code: str) -> str:
    if target_lang_code == "en":
        return text
    
    cache_key = f"{text}_{target_lang_code}"
    if cache_key in translation_cache:
        return translation_cache[cache_key]
    
    wait_for_api_limit()
    
    target_lang = LANGUAGES[target_lang_code]
    prompt = f"Translate the following English text to {target_lang}. Return only the translated text, no explanations or alternatives: {text}"
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
            return text
        raise
    
    translated = response.text.strip()
    if translated.startswith("```"):
        translated = translated[3:].strip()
    if translated.endswith("```"):
        translated = translated[:-3].strip()
    
    translation_cache[cache_key] = translated
    return translated

# Handlers

# Start command handler

@router.message(Command("start"))
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=name, callback_data=f"lang_{code}") for code, name in LANGUAGES.items()
        ]
    ])
    
    await message.answer(
        "Please select your native language / Тілді таңдаңыз / Выберите родной язык:",
        reply_markup=keyboard
    )

# Language selection handler

@router.callback_query(lambda c: c.data.startswith("lang_"))
async def language_selected(callback: CallbackQuery):
    lang_code = callback.data.replace("lang_", "")
    user = get_user(callback.from_user.id)
    user["native_lang"] = LANGUAGES[lang_code]
    user["native_lang_code"] = lang_code
    user["mission"] = 1
    user["stage"] = 1
    
    await callback.message.answer(
        TRANSLATIONS["lang_set"][lang_code].format(lang=user["native_lang"])
    )
    await asyncio.sleep(0.5)
    
    await callback.message.answer(
        TRANSLATIONS["use_help"][lang_code]
    )
    await asyncio.sleep(0.5)
    
    await callback.message.answer(
        TRANSLATIONS["help_message"][lang_code]
    )
    
    await callback.answer()
    
# Help command handler

@router.message(Command("help"))
async def help_handler(message: Message):
    user = get_user(message.from_user.id)
    lang_code = user["native_lang_code"] if user["native_lang_code"] else "en"
    
    await message.answer(TRANSLATIONS["help_message"][lang_code])

# Progress command handler

@router.message(Command("progress"))
async def progress_handler(message: Message):
    user = get_user(message.from_user.id)
    lang_code = user["native_lang_code"] if user["native_lang_code"] else "en"
    
    if not user["native_lang_code"]:
        await message.answer(TRANSLATIONS["no_lang"]["en"])
        return
    
    # Calculate XP for current level
    
    xp_per_level = 10
    current_level_xp = user["level"] if isinstance(user.get("level"), int) else LANGUAGE_LEVELS.index(user.get("level", "A1"))
    xp_needed_for_next = (current_level_xp + 1) * xp_per_level
    xp_to_next = max(0, xp_needed_for_next - user["xp"])
    
    await message.answer(
        TRANSLATIONS["progress_message"][lang_code].format(
            level=user["level"],
            xp=user["xp"],
            xp_to_next=xp_to_next
        )
    )

# Quest command handler

@router.message(Command("quest"))
async def quest_start_handler(message: Message):
    user = get_user(message.from_user.id)
    lang_code = user["native_lang_code"] if user["native_lang_code"] else "en"
    
    if not user["native_lang_code"]:
        await message.answer(TRANSLATIONS["no_lang"]["en"])
        return
    
    if user["mission"] != 1 or user["stage"] > len(mission_1["stages"]):
        user["mission"] = 1
        user["stage"] = 1
    
    current_stage = mission_1["stages"][user["stage"] - 1]
    translated_npc = translate_text(current_stage["npc_text"], lang_code)
    
    if current_stage["input_type"] == "inline_keyboard":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=option["text"], callback_data=f"answer_{user['stage']}_{i}")] 
            for i, option in enumerate(current_stage["options"])
        ])
        await message.answer(translated_npc, reply_markup=keyboard)
    else:
        await message.answer(translated_npc, parse_mode="Markdown")

# Quest handler

@router.message()
async def quest_handler(message: Message):
    if message.text.startswith("/"):
        return
    
    user = get_user(message.from_user.id)
    
    if not user["native_lang_code"]:
        await message.answer(TRANSLATIONS["no_lang"]["en"])
        return
    
    if user["mission"] != 1:
        await message.answer(TRANSLATIONS["completed_all"][user["native_lang_code"]])
        return
    
    if user["stage"] > len(mission_1["stages"]):
        user["mission"] += 1
        await message.answer(TRANSLATIONS["completed_all"][user["native_lang_code"]])
        return
    
    current_stage = mission_1["stages"][user["stage"] - 1]
    
    if current_stage["input_type"] == "inline_keyboard":
        translated_npc = translate_text(current_stage["npc_text"], user["native_lang_code"])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=option["text"], callback_data=f"answer_{user['stage']}_{i}")] 
            for i, option in enumerate(current_stage["options"])
        ])
        await message.answer(translated_npc, reply_markup=keyboard)
        return
    elif current_stage["input_type"] != "text_free":
        await message.answer(TRANSLATIONS["wrong_input_type"][user["native_lang_code"]])
        return
    
    result = llm_check(
        user_text=message.text,
        stage=current_stage,
        explain_lang=user["native_lang"],
        native_lang_code=user["native_lang_code"]
    )
    
    if result["correct"]:
        xp_gain = mission_1["reward_xp"] // len(mission_1["stages"])
        user["xp"] += xp_gain
        user["stage"] += 1
        
        await message.answer(
            f"{result['feedback']}\n" +
            TRANSLATIONS["xp_gain"][user["native_lang_code"]].format(xp=xp_gain)
        )
        
        if user["stage"] <= len(mission_1["stages"]):
            await asyncio.sleep(0.5)
            next_stage = mission_1["stages"][user["stage"] - 1]
            translated_npc = translate_text(next_stage["npc_text"], user["native_lang_code"])
            
            if next_stage["input_type"] == "inline_keyboard":
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=option["text"], callback_data=f"answer_{user['stage']}_{i}")] 
                    for i, option in enumerate(next_stage["options"])
                ])
                await message.answer(translated_npc, reply_markup=keyboard)
            else:
                await message.answer(translated_npc, parse_mode="Markdown")
        else:
            await asyncio.sleep(0.5)
            await message.answer(TRANSLATIONS["completed_all"][user["native_lang_code"]])
    else:
        
        await message.answer(f"{result['feedback']}")

# Inline keyboard answer handler

@router.callback_query(lambda c: c.data.startswith("answer_"))
async def inline_keyboard_answer(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    
    parts = callback.data.split("_")
    stage_num = int(parts[1])
    option_idx = int(parts[2])
    
    if user["stage"] != stage_num:
        await callback.answer("This is not the current stage.", show_alert=True)
        return
    
    current_stage = mission_1["stages"][user["stage"] - 1]
    selected_option = current_stage["options"][option_idx]
    
    if selected_option["correct"]:
        xp_gain = mission_1["reward_xp"] // len(mission_1["stages"])
        user["xp"] += xp_gain
        user["stage"] += 1
        
        await callback.message.answer(
            f"{TRANSLATIONS['correct_answer'][user['native_lang_code']]}\n{current_stage.get('explanation', '')}\n" +
            TRANSLATIONS["xp_gain"][user["native_lang_code"]].format(xp=xp_gain)
        )
        
        if user["stage"] <= len(mission_1["stages"]):
            await asyncio.sleep(0.5)
            next_stage = mission_1["stages"][user["stage"] - 1]
            
            if user["stage"] == 3:
                context_hint = translate_text("(Tom answered: I want milk)", user["native_lang_code"])
                await callback.message.answer(context_hint)
                await asyncio.sleep(0.3)
            
            if next_stage["input_type"] == "inline_keyboard":
                translated_npc = translate_text(next_stage["npc_text"], user["native_lang_code"])
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=option["text"], callback_data=f"answer_{user['stage']}_{i}")] 
                    for i, option in enumerate(next_stage["options"])
                ])
                await callback.message.answer(translated_npc, reply_markup=keyboard)
            else:
                translated_npc = translate_text(next_stage["npc_text"], user["native_lang_code"])
                await callback.message.answer(translated_npc, parse_mode="Markdown")
        else:
            await asyncio.sleep(0.5)
            await callback.message.answer(TRANSLATIONS["completed_all"][user["native_lang_code"]])
    else:
        await callback.message.answer(
            f"{TRANSLATIONS['incorrect_try_again'][user['native_lang_code']]}\n{current_stage.get('explanation', '')}"
        )
    
    await callback.answer()
        
# Run bot

async def main():
    await dp.start_polling(bot)
    print("Bot started")
    
if __name__ == "__main__":
    asyncio.run(main())





