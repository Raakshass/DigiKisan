import 'package:flutter/material.dart';
import '../services/translation_service.dart';
import '../core/app_export.dart';

class LanguageSelector extends StatelessWidget {
  final String selectedLanguage;
  final String selectedLanguageName;
  final Function(String languageCode, String languageName) onLanguageChanged;

  const LanguageSelector({
    Key? key,
    required this.selectedLanguage,
    required this.selectedLanguageName,
    required this.onLanguageChanged,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      icon: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.language, 
            color: appTheme.colorFF065F, 
            size: 16
          ),
          SizedBox(width: 4.h),
          Text(
            selectedLanguageName,
            style: TextStyleHelper.instance.body12
                .copyWith(color: appTheme.colorFF065F),
          ),
        ],
      ),
      onSelected: (String languageCode) {
        String languageName = TranslationService.supportedLanguages.entries
            .firstWhere((entry) => entry.value == languageCode)
            .key;
        onLanguageChanged(languageCode, languageName);
      },
      itemBuilder: (BuildContext context) {
        return TranslationService.supportedLanguages.entries.map((entry) {
          return PopupMenuItem<String>(
            value: entry.value,
            child: Row(
              children: [
                if (entry.value == selectedLanguage) 
                  Icon(Icons.check, color: appTheme.colorFF065F, size: 16),
                SizedBox(width: 8.h),
                Text(entry.key),
              ],
            ),
          );
        }).toList();
      },
    );
  }
}
