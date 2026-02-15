MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "welcome": (
            "Welcome to Telegram Ads Marketplace!\n\n"
            "Buy and sell advertising in Telegram channels — "
            "with verified analytics, secure escrow, and auto-posting.\n\n"
            "Use the buttons below to get started."
        ),
        "help": (
            "This bot helps you buy and sell advertising in Telegram channels.\n\n"
            "As an <b>Advertiser</b>, you can search channels, create campaigns, "
            "and pay via TON escrow.\n\n"
            "As a <b>Channel Owner</b>, you can list your channels, manage deals, "
            "and receive payments.\n\n"
            "Open the Mini App for the full experience!"
        ),
        "no_deals": "You don't have any deals yet. Open the Mini App to get started!",
        "btn_open_app": "Open Mini App",
        "btn_my_deals": "My Deals",
        "btn_help": "Help",
        "channel_added": (
            "Channel <b>{title}</b> (@{username}) has been added successfully!\n\n"
            "Subscribers: {subscribers}\n"
            "You can now create listings for this channel."
        ),
        "channel_connected": (
            "Channel <b>{title}</b> has been connected!\n\n"
            "The bot is now an admin and can track stats and auto-post."
        ),
        "channel_disconnected": (
            "Bot has been removed from channel <b>{title}</b>.\n\n"
            "Stats tracking and auto-posting are no longer available for this channel."
        ),
        "channel_verified": (
            "Stats for <b>{title}</b> have been verified.\n\n"
            "Subscribers: {subscribers}"
        ),
        "new_deal_advertiser": (
            "Your deal for <b>{listing_title}</b> has been created.\n\n"
            "Price: {price} {currency}\n"
            "Status: Draft\n\n"
            "Open the Mini App to manage this deal."
        ),
        "new_deal_owner": (
            "New deal request for <b>{listing_title}</b>!\n\n"
            "Advertiser: {advertiser_name}\n"
            "Price: {price} {currency}\n\n"
            "Open the Mini App to review this deal."
        ),
        "campaign_created": (
            "Campaign <b>{title}</b> has been created.\n\n"
            "Budget: {budget_min}–{budget_max} TON\n"
            "Open the Mini App to manage your campaigns."
        ),
        "deals_list_header": "Your deals:",
        "deals_list_item": "#{deal_id} — {status} — {price} {currency}",
        "deals_active_header": "Your active deals:",
        "deals_cat_scheduled": "{count} scheduled",
        "deals_cat_published": "{count} published",
        "deals_cat_completed": "{count} completed",
        "deals_cat_drafts": "{count} draft(s)",
        "deals_cat_cancelled": "{count} cancelled",
        "no_active_deals": "No active deals right now.",
        "deals_also": "Also: {categories}",
        "deals_view_all_app": "View All Deals",
        "deal_status_changed": (
            "Deal #{deal_id} status changed to <b>{status}</b>.\n\n"
            "Open the Mini App for details."
        ),
        "deal_new_message": (
            "New message in deal #{deal_id} from {sender_name}:\n\n"
            "{text}"
        ),
        # Deal messaging (bot FSM)
        "deal_msg_prompt": "Send your message for deal #{deal_id} — text, photo, video, or any combination. Send /cancel to abort.",
        "deal_msg_sent": "Message sent to deal #{deal_id}.",
        "deal_msg_error": "Failed to send message. Please try again.",
        "deal_msg_empty": "Please send a text message, photo, video, or document.",
        "deal_msg_text_only": "Please send a text message only.",
        # Creative submission (bot FSM)
        "creative_prompt": "Compose your post as it should appear in the channel — text, photo, video, or text with media. Send it as a single message.\n\nSend /cancel to abort.",
        "creative_empty": "Please send text, a photo, video, or document. The message cannot be empty.",
        "creative_confirm": "Above is your creative preview.",
        "creative_confirm_btn": "✅ Submit",
        "creative_cancel_btn": "❌ Cancel",
        "creative_submitted": "Creative submitted for deal #{deal_id} and sent for review.",
        "creative_submit_error": "Failed to submit creative. Please try again.",
        # Creative review (advertiser)
        "creative_feedback_prompt": "Enter your feedback for the creative. Send /cancel to abort.",
        "creative_approved": "Creative approved for deal #{deal_id}!",
        "creative_approve_error": "Failed to approve creative. Please try again.",
        "creative_changes_sent": "Changes requested for deal #{deal_id}.",
        "creative_changes_error": "Failed to request changes. Please try again.",
        # Schedule
        "schedule_prompt": "Enter the posting date and time (YYYY-MM-DD HH:MM). Send /cancel to abort.",
        "schedule_invalid": "Invalid format. Please use YYYY-MM-DD HH:MM.",
        "schedule_confirm": (
            "Schedule post for: {datetime}\n\n"
            "Send /confirm to schedule, or /cancel to abort."
        ),
        "schedule_success": "Post scheduled for deal #{deal_id}.",
        "schedule_error": "Failed to schedule post. Please try again.",
        # Posting events
        "post_published": "Post published for deal #{deal_id}!",
        "retention_passed": "Retention check passed for deal #{deal_id}. Payment released!",
        "retention_failed": "Retention check failed for deal #{deal_id}. Payment refunded.",
        # Deal transitions
        "deal_transition_success": "Deal #{deal_id} updated to <b>{status}</b>.",
        "deal_transition_error": "Failed to update deal. Please try again.",
        # Deal detail (bot view)
        "deal_not_found": "Deal not found or you don't have access.",
        "deal_detail_bot": (
            "Deal #{deal_id}\n"
            "Status: <b>{status}</b>\n"
            "Price: {price} {currency}"
            "{wallet_line}"
            "{escrow_line}"
        ),
        # Deal brief FSM
        "deal_brief_prompt": "Enter the ad brief for this deal (required). Send /cancel to abort.",
        "deal_publish_from_prompt": "Enter publish-from date (YYYY-MM-DD) or send /skip.",
        "deal_publish_to_prompt": "Enter publish-to date (YYYY-MM-DD) or send /skip.",
        "deal_publish_date_invalid": "Invalid date format. Please use YYYY-MM-DD or send /skip.",
        "deal_brief_confirm": (
            "Deal brief summary:\n"
            "Brief: {brief}\n"
            "Publish from: {publish_from}\n"
            "Publish to: {publish_to}\n\n"
            "Send /confirm to save and send, or /cancel to abort."
        ),
        "deal_brief_saved": "Brief saved and deal sent to the channel owner.",
        "deal_brief_save_error": "Failed to save brief. Please try again.",
        "deal_brief_required": "Brief is required before sending the deal. Please fill in the brief first.",
        # Amendment proposal FSM
        "amendment_price_prompt": "Enter proposed price or send /skip.",
        "amendment_publish_date_prompt": "Enter proposed publish date (YYYY-MM-DD) or send /skip.",
        "amendment_confirm": (
            "Amendment proposal:\n"
            "Price: {price}\n"
            "Publish date: {publish_date}\n\n"
            "Send /confirm to propose, or /cancel to abort."
        ),
        "amendment_sent": "Amendment proposal sent to the advertiser.",
        "amendment_error": "Failed to send amendment proposal. Please try again.",
        "amendment_nothing": "You must propose at least one change.",
        # Amendment resolution
        "amendment_accepted": "Amendment accepted. Deal updated.",
        "amendment_rejected": "Amendment rejected.",
        "amendment_resolve_error": "Failed to process amendment. Please try again.",
        "amendment_proposed": "The channel owner proposed changes to deal #{deal_id}.",
        # Skip
        "skipped": "Skipped.",
        # Escrow
        "escrow_use_mini_app": "Escrow requires a TON wallet. Please open the Mini App to create the escrow and send the deposit.",
        # Wallet required
        "wallet_required_deal": "Please connect your TON wallet in the Mini App (Profile → Connect Wallet) to proceed with this deal.",
        # Cancel FSM
        "nothing_to_cancel": "Nothing to cancel.",
        "cancelled": "Action cancelled.",
    },
    "ru": {
        "welcome": (
            "Добро пожаловать в маркетплейс рекламы Telegram!\n\n"
            "Покупайте и продавайте рекламу в Telegram-каналах — "
            "с верифицированной аналитикой, безопасным escrow и авто-постингом.\n\n"
            "Используйте кнопки ниже, чтобы начать."
        ),
        "help": (
            "Этот бот помогает вам покупать и продавать рекламу в Telegram-каналах.\n\n"
            "Как <b>рекламодатель</b>, вы можете искать каналы, создавать кампании "
            "и платить через TON escrow.\n\n"
            "Как <b>владелец канала</b>, вы можете размещать свои каналы, управлять сделками "
            "и получать выплаты.\n\n"
            "Откройте Mini App для полного доступа!"
        ),
        "no_deals": "У вас пока нет сделок. Откройте Mini App, чтобы начать!",
        "btn_open_app": "Открыть Mini App",
        "btn_my_deals": "Мои сделки",
        "btn_help": "Помощь",
        "channel_added": (
            "Канал <b>{title}</b> (@{username}) успешно добавлен!\n\n"
            "Подписчиков: {subscribers}\n"
            "Теперь вы можете создавать листинги для этого канала."
        ),
        "channel_connected": (
            "Канал <b>{title}</b> подключён!\n\n"
            "Бот теперь является администратором и может отслеживать статистику и авто-постить."
        ),
        "channel_disconnected": (
            "Бот удалён из канала <b>{title}</b>.\n\n"
            "Отслеживание статистики и авто-постинг больше недоступны для этого канала."
        ),
        "channel_verified": (
            "Статистика канала <b>{title}</b> подтверждена.\n\n"
            "Подписчиков: {subscribers}"
        ),
        "new_deal_advertiser": (
            "Ваша сделка по <b>{listing_title}</b> создана.\n\n"
            "Цена: {price} {currency}\n"
            "Статус: Черновик\n\n"
            "Откройте Mini App для управления сделкой."
        ),
        "new_deal_owner": (
            "Новый запрос на сделку по <b>{listing_title}</b>!\n\n"
            "Рекламодатель: {advertiser_name}\n"
            "Цена: {price} {currency}\n\n"
            "Откройте Mini App для просмотра."
        ),
        "campaign_created": (
            "Кампания <b>{title}</b> создана.\n\n"
            "Бюджет: {budget_min}–{budget_max} TON\n"
            "Откройте Mini App для управления кампаниями."
        ),
        "deals_list_header": "Ваши сделки:",
        "deals_list_item": "#{deal_id} — {status} — {price} {currency}",
        "deals_active_header": "Ваши активные сделки:",
        "deals_cat_scheduled": "{count} запланир.",
        "deals_cat_published": "{count} опублик.",
        "deals_cat_completed": "{count} завершён.",
        "deals_cat_drafts": "{count} черновик(ов)",
        "deals_cat_cancelled": "{count} отменён.",
        "no_active_deals": "Нет активных сделок.",
        "deals_also": "Также: {categories}",
        "deals_view_all_app": "Все сделки",
        "deal_status_changed": (
            "Статус сделки #{deal_id} изменён на <b>{status}</b>.\n\n"
            "Откройте Mini App для деталей."
        ),
        "deal_new_message": (
            "Новое сообщение в сделке #{deal_id} от {sender_name}:\n\n"
            "{text}"
        ),
        # Deal messaging (bot FSM)
        "deal_msg_prompt": "Отправьте сообщение для сделки #{deal_id} — текст, фото, видео или любую комбинацию. Отправьте /cancel для отмены.",
        "deal_msg_sent": "Сообщение отправлено в сделку #{deal_id}.",
        "deal_msg_error": "Не удалось отправить сообщение. Попробуйте ещё раз.",
        "deal_msg_empty": "Отправьте текст, фото, видео или документ. Сообщение не может быть пустым.",
        "deal_msg_text_only": "Пожалуйста, отправьте только текстовое сообщение.",
        # Creative submission (bot FSM)
        "creative_prompt": "Составьте пост так, как он должен выглядеть в канале — текст, фото, видео или текст с медиа. Отправьте одним сообщением.\n\nОтправьте /cancel для отмены.",
        "creative_empty": "Отправьте текст, фото, видео или документ. Сообщение не может быть пустым.",
        "creative_confirm": "Выше превью вашего креатива.",
        "creative_confirm_btn": "✅ Отправить",
        "creative_cancel_btn": "❌ Отмена",
        "creative_submitted": "Креатив для сделки #{deal_id} отправлен на проверку.",
        "creative_submit_error": "Не удалось отправить креатив. Попробуйте ещё раз.",
        # Creative review (advertiser)
        "creative_feedback_prompt": "Введите ваш отзыв по креативу. Отправьте /cancel для отмены.",
        "creative_approved": "Креатив одобрен для сделки #{deal_id}!",
        "creative_approve_error": "Не удалось одобрить креатив. Попробуйте ещё раз.",
        "creative_changes_sent": "Изменения запрошены для сделки #{deal_id}.",
        "creative_changes_error": "Не удалось запросить изменения. Попробуйте ещё раз.",
        # Schedule
        "schedule_prompt": "Введите дату и время публикации (ГГГГ-ММ-ДД ЧЧ:ММ). Отправьте /cancel для отмены.",
        "schedule_invalid": "Неверный формат. Используйте ГГГГ-ММ-ДД ЧЧ:ММ.",
        "schedule_confirm": (
            "Запланировать пост на: {datetime}\n\n"
            "Отправьте /confirm для планирования, или /cancel для отмены."
        ),
        "schedule_success": "Пост запланирован для сделки #{deal_id}.",
        "schedule_error": "Не удалось запланировать пост. Попробуйте ещё раз.",
        # Posting events
        "post_published": "Пост опубликован для сделки #{deal_id}!",
        "retention_passed": "Проверка удержания пройдена для сделки #{deal_id}. Оплата переведена!",
        "retention_failed": "Проверка удержания не пройдена для сделки #{deal_id}. Оплата возвращена.",
        # Deal transitions
        "deal_transition_success": "Сделка #{deal_id} обновлена до <b>{status}</b>.",
        "deal_transition_error": "Не удалось обновить сделку. Попробуйте ещё раз.",
        # Deal detail (bot view)
        "deal_not_found": "Сделка не найдена или у вас нет доступа.",
        "deal_detail_bot": (
            "Сделка #{deal_id}\n"
            "Статус: <b>{status}</b>\n"
            "Цена: {price} {currency}"
            "{wallet_line}"
            "{escrow_line}"
        ),
        # Deal brief FSM
        "deal_brief_prompt": "Введите рекламное задание (brief) для этой сделки (обязательно). Отправьте /cancel для отмены.",
        "deal_publish_from_prompt": "Введите дату публикации «с» (ГГГГ-ММ-ДД) или отправьте /skip.",
        "deal_publish_to_prompt": "Введите дату публикации «до» (ГГГГ-ММ-ДД) или отправьте /skip.",
        "deal_publish_date_invalid": "Неверный формат даты. Используйте ГГГГ-ММ-ДД или отправьте /skip.",
        "deal_brief_confirm": (
            "Описание сделки:\n"
            "Задание: {brief}\n"
            "Публикация с: {publish_from}\n"
            "Публикация до: {publish_to}\n\n"
            "Отправьте /confirm для сохранения и отправки, или /cancel для отмены."
        ),
        "deal_brief_saved": "Задание сохранено. Сделка отправлена владельцу канала.",
        "deal_brief_save_error": "Не удалось сохранить задание. Попробуйте ещё раз.",
        "deal_brief_required": "Необходимо заполнить задание (brief) перед отправкой сделки.",
        # Amendment proposal FSM
        "amendment_price_prompt": "Введите предлагаемую цену или отправьте /skip.",
        "amendment_publish_date_prompt": "Введите предлагаемую дату публикации (ГГГГ-ММ-ДД) или отправьте /skip.",
        "amendment_confirm": (
            "Предложение об изменениях:\n"
            "Цена: {price}\n"
            "Дата публикации: {publish_date}\n\n"
            "Отправьте /confirm для отправки, или /cancel для отмены."
        ),
        "amendment_sent": "Предложение об изменениях отправлено рекламодателю.",
        "amendment_error": "Не удалось отправить предложение. Попробуйте ещё раз.",
        "amendment_nothing": "Необходимо предложить хотя бы одно изменение.",
        # Amendment resolution
        "amendment_accepted": "Изменения приняты. Сделка обновлена.",
        "amendment_rejected": "Изменения отклонены.",
        "amendment_resolve_error": "Не удалось обработать предложение. Попробуйте ещё раз.",
        "amendment_proposed": "Владелец канала предложил изменения по сделке #{deal_id}.",
        # Skip
        "skipped": "Пропущено.",
        # Escrow
        "escrow_use_mini_app": "Для эскроу необходим TON-кошелёк. Откройте Mini App, чтобы создать эскроу и отправить депозит.",
        # Wallet required
        "wallet_required_deal": "Подключите TON-кошелёк в Mini App (Профиль → Подключить кошелёк), чтобы продолжить работу со сделкой.",
        # Cancel FSM
        "nothing_to_cancel": "Нечего отменять.",
        "cancelled": "Действие отменено.",
    },
}
