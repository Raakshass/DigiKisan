import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../../core/app_export.dart';
import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import '../../services/image_service.dart';
import '../../services/translation_service.dart';
import '../auth_screen/login_screen.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:path_provider/path_provider.dart';

// Composable widgets
import 'widgets/chat_header.dart';
import 'widgets/chat_home_view.dart';
import 'widgets/chat_input_bar.dart';
import 'widgets/chat_message_bubble.dart';

/// KisanMitra AI Chat Screen — v2.0 (Refactored)
///
/// Architecture:
///   ChatScreen (state + business logic)
///   ├── ChatHeader (menu, title, language, logout)
///   ├── ChatHomeView (welcome, cards, quick actions)  — when not in conversation
///   ├── ConversationView (message list)                — when in conversation
///   │   └── ChatMessageBubble × N
///   └── ChatInputBar (text, voice, camera, send)
///
/// Business logic stays here; rendering is delegated to widgets.
class ChatScreen extends StatefulWidget {
  const ChatScreen({Key? key}) : super(key: key);

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  // --- Controllers ---
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  // --- Audio ---
  FlutterSoundRecorder? _recorder;
  FlutterSoundPlayer? _player;
  bool _isRecording = false;
  bool _isPlayingResponse = false;
  String? _recordingPath;

  // --- User ---
  String? _userName;
  String? _userEmail;

  // --- Session ---
  String? _currentSessionId;
  bool _sessionInitialized = false;

  // --- Conversation ---
  Map<String, dynamic> _sessionState = {};
  final List<Map<String, String>> _conversationHistory = [];
  bool _inConversation = false;
  bool _isLoading = false;

  // --- Disease ---
  bool _isDiseaseConversationActive = false;
  String _currentDiseaseContext = "";

  // --- Language ---
  String _selectedLanguage = 'en-IN';
  String _selectedLanguageName = 'English';

  // --- Location (for region-specific RAG) ---
  Map<String, String>? _userLocation;

  // ===========================================================================
  // Lifecycle
  // ===========================================================================

  @override
  void initState() {
    super.initState();
    _loadUserInfo();
    _initializeChatSession();
    _initializeAudio();
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _recorder?.closeRecorder();
    _player?.closePlayer();
    super.dispose();
  }

  // ===========================================================================
  // Initialization
  // ===========================================================================

  void _loadUserInfo() {
    final userInfo = AuthService.userInfo;
    if (userInfo != null) {
      setState(() {
        _userName = userInfo['full_name'] ?? 'User';
        _userEmail = userInfo['email'] ?? '';
        _userLocation = AuthService.locationPayload;
      });
    }
  }

  void _initializeAudio() async {
    _recorder = FlutterSoundRecorder();
    _player = FlutterSoundPlayer();

    await Permission.microphone.request();
    await Permission.storage.request();

    await _recorder!.openRecorder();
    await _player!.openPlayer();
  }

  Future<void> _initializeChatSession() async {
    if (_sessionInitialized) return;

    try {
      final response = await ApiService.startChatSession();
      if (response['ok'] == true) {
        setState(() {
          _currentSessionId = response['session_id'];
          _sessionInitialized = true;
        });

        _conversationHistory.add({
          'sender': 'bot',
          'text': response['message'] ??
              'Welcome to KisanMitra AI! How can I help you today?',
          'language': _selectedLanguage,
        });
      }
    } catch (e) {
      print('❌ Session creation error: $e');
    }
  }

  // ===========================================================================
  // Voice Recording
  // ===========================================================================

  void _toggleVoiceRecording() async {
    if (_isRecording) {
      await _stopRecording();
    } else {
      await _startRecording();
    }
  }

  Future<void> _startRecording() async {
    try {
      setState(() => _isRecording = true);

      final directory = await getTemporaryDirectory();
      _recordingPath =
          '${directory.path}/voice_${DateTime.now().millisecondsSinceEpoch}.wav';

      await _recorder!.startRecorder(
        toFile: _recordingPath,
        codec: Codec.pcm16WAV,
        sampleRate: 16000,
      );

      // Auto-stop after 30 seconds
      Future.delayed(const Duration(seconds: 30), () {
        if (_isRecording) _stopRecording();
      });
    } catch (e) {
      print('❌ Recording start error: $e');
      setState(() => _isRecording = false);
      _showSnackBar('Failed to start recording');
    }
  }

  Future<void> _stopRecording() async {
    try {
      setState(() => _isRecording = false);
      await _recorder!.stopRecorder();

      if (_recordingPath != null && File(_recordingPath!).existsSync()) {
        final audioFile = File(_recordingPath!);
        final audioBytes = await audioFile.readAsBytes();

        final transcript = await TranslationService.speechToTextTranslate(
          audioBytes: audioBytes,
        );

        if (transcript != null && transcript.trim().isNotEmpty) {
          _textController.text = transcript;
          await _sendMessageHandler();
        } else {
          _showSnackBar('No speech detected. Please try again.');
        }

        await audioFile.delete();
      }
    } catch (e) {
      print('❌ Recording stop error: $e');
      _showSnackBar('Error processing voice input');
      setState(() => _isRecording = false);
    }
  }

  Future<void> _playResponseAsVoice(String text) async {
    if (_isPlayingResponse || text.trim().isEmpty) return;

    try {
      setState(() => _isPlayingResponse = true);

      final audioBytes = await TranslationService.textToSpeech(
        text: text,
        targetLanguageCode: _selectedLanguage,
      );

      if (audioBytes != null) {
        final tempDir = await getTemporaryDirectory();
        final tempFile = File(
          '${tempDir.path}/response_${DateTime.now().millisecondsSinceEpoch}.wav',
        );
        await tempFile.writeAsBytes(audioBytes);

        await _player!.startPlayer(
          fromURI: tempFile.path,
          whenFinished: () {
            setState(() => _isPlayingResponse = false);
            tempFile.delete();
          },
        );
      } else {
        setState(() => _isPlayingResponse = false);
      }
    } catch (e) {
      print('❌ TTS playback error: $e');
      setState(() => _isPlayingResponse = false);
    }
  }

  // ===========================================================================
  // Message Handling
  // ===========================================================================

  Future<void> _sendMessageHandler() async {
    final message = _textController.text.trim();
    if (message.isEmpty) return;

    setState(() {
      _isLoading = true;
      _inConversation = true;
    });

    _conversationHistory.add({
      'sender': 'user',
      'text': message,
      'language': _selectedLanguage,
    });
    _scrollToBottom();

    try {
      // Translate to English if needed
      String englishMessage = message;
      if (_selectedLanguage != 'en-IN') {
        englishMessage = await TranslationService.translateText(
          message, _selectedLanguage, 'en-IN',
        );
        englishMessage =
            englishMessage.trim().replaceAll(RegExp(r'[.,;!]+$'), '');
      }

      // Try authenticated messaging first
      if (AuthService.token != null) {
        await _sendMessageWithAuth(englishMessage);
        _textController.clear();
        setState(() => _isLoading = false);
        _scrollToBottom();
        return;
      }

      // Fallback: unauthenticated flow
      String botResponse = '';

      // Disease conversation
      if (_isDiseaseConversationActive && _currentDiseaseContext.isNotEmpty) {
        try {
          final concise =
              await _sendDiseaseChat(englishMessage, _currentDiseaseContext);
          botResponse = concise;
        } catch (_) {
          _isDiseaseConversationActive = false;
          _currentDiseaseContext = "";
        }
      }

      // Slot filling / classification
      if (botResponse.isEmpty) {
        if (_sessionState.isNotEmpty &&
            _sessionState['in_slot_fill'] == true) {
          final result =
              await ApiService.chatWithSlots(englishMessage, _sessionState);
          botResponse = _crispify(result['response'] ?? '');
          _sessionState = result['session_state'] ?? {};
          if (result['completed'] == true) {
            _sessionState = {};
            botResponse += "\nAnything else?";
          }
        } else {
          final classification =
              await ApiService.classifyText(englishMessage);
          final intent = classification['result']['prediction'];
          if (intent == 'price_enquiry') {
            final result =
                await ApiService.chatWithSlots(englishMessage, _sessionState);
            botResponse = _crispify(result['response'] ?? '');
            _sessionState = result['session_state'] ?? {};
          } else {
            // General chat via RAG-augmented endpoint
            final result = await ApiService.sendChatMessage(
              englishMessage,
              sessionId: _currentSessionId,
              sessionState: _sessionState,
              location: _userLocation,
              language: _selectedLanguage.split('-').first, // 'en-IN' -> 'en'
            );
            botResponse = _crispify(result['response'] ?? '');
          }
        }
      }

      // Translate response
      String display = botResponse;
      if (_selectedLanguage != 'en-IN') {
        display = await TranslationService.translateText(
          _limitForTranslate(botResponse, maxChars: 900),
          'en-IN',
          _selectedLanguage,
        );
      }

      _conversationHistory.add({
        'sender': 'bot',
        'text': display,
        'language': _selectedLanguage,
      });

      await _playResponseAsVoice(display);
      _textController.clear();
    } catch (e) {
      print('❌ API Error: $e');
      String errorMsg =
          "Having connection trouble. Please try again, or restart the app.";
      if (_selectedLanguage != 'en-IN') {
        try {
          errorMsg = await TranslationService.translateText(
            errorMsg, 'en-IN', _selectedLanguage,
          );
        } catch (_) {}
      }
      _conversationHistory.add({
        'sender': 'bot',
        'text': errorMsg,
        'language': _selectedLanguage,
      });
    }

    setState(() => _isLoading = false);
    _scrollToBottom();
  }

  Future<void> _sendMessageWithAuth(String message) async {
    try {
      final response = await AuthService.sendChatMessage(message);

      if (response != null) {
        final botResponse = response['response'] ?? 'No response received';
        _conversationHistory.add({
          'sender': 'bot',
          'text': botResponse,
          'language': _selectedLanguage,
        });
        await _playResponseAsVoice(botResponse);
        return;
      }
    } catch (e) {
      print('❌ Authenticated message error: $e');
    }

    // Fallback
    _sendMessageHandler();
  }

  Future<String> _sendDiseaseChat(
      String message, String diseaseContext) async {
    final res = await ApiService.sendDiseaseChat(message, diseaseContext);
    if (res['ok'] == true) {
      return _crispify(res['response'] as String);
    }
    throw Exception(res['error'] ?? 'Disease chat API error');
  }

  // ===========================================================================
  // Image Upload
  // ===========================================================================

  void _handleImageUpload() async {
    try {
      setState(() => _isLoading = true);

      final XFile? selectedImage =
          await ImageService.showImageSourceDialog(context);
      if (selectedImage == null) {
        setState(() => _isLoading = false);
        return;
      }

      final imageBytes = await selectedImage.readAsBytes();
      _conversationHistory.add({
        'sender': 'user',
        'text': '📸 Uploaded crop image for diagnosis',
        'language': _selectedLanguage,
        'image_path': selectedImage.path,
        'image_bytes': base64Encode(imageBytes),
      });

      final result =
          await ImageService.uploadForDiseaseDetection(selectedImage);

      if (result['conversation_started'] == true &&
          result['prediction'] != null) {
        setState(() {
          _isDiseaseConversationActive = true;
          _currentDiseaseContext = result['prediction'];
          _inConversation = true;
        });
      }

      final raw = (result['ai_summary'] as String?) ??
          _formatDiseaseResponse(result);
      final crisp = _crispify(raw);
      final toTranslate = _limitForTranslate(crisp, maxChars: 900);

      String reply = toTranslate;
      if (_selectedLanguage != 'en-IN') {
        reply = await TranslationService.translateText(
          toTranslate, 'en-IN', _selectedLanguage,
        );
      }

      _conversationHistory.add({
        'sender': 'bot',
        'text': reply,
        'language': _selectedLanguage,
      });

      await _playResponseAsVoice(reply);
    } catch (e) {
      print('❌ Image upload error: $e');
      _conversationHistory.add({
        'sender': 'bot',
        'text':
            "Couldn't analyze the image. Please try again with a clear photo.",
        'language': _selectedLanguage,
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }

  // ===========================================================================
  // Helpers
  // ===========================================================================

  void _resetConversation() {
    setState(() {
      _inConversation = false;
      _conversationHistory.clear();
      _sessionState = {};
      _isDiseaseConversationActive = false;
      _currentDiseaseContext = "";
    });

    _sessionInitialized = false;
    _currentSessionId = null;
    _initializeChatSession();
  }

  void _logout() async {
    await AuthService.clearAuthData();
    if (mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => LoginScreen()),
      );
    }
  }

  void _handleQuickAction(String message) {
    _textController.text = message;
    _sendMessageHandler();
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), duration: const Duration(seconds: 2)),
    );
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  String _stripMarkdown(String s) =>
      s
          .replaceAll(RegExp(r'[*`#>•\-]+'), '')
          .replaceAll(RegExp(r'\s+\n'), '\n')
          .replaceAll(RegExp(r'\n{2,}'), '\n')
          .replaceAll(RegExp(r' {2,}'), ' ')
          .trim();

  String _crispify(String s, {int maxChars = 350}) {
    final t = _stripMarkdown(s);
    if (t.length <= maxChars) return t;
    final cut = t.substring(0, maxChars);
    final dot = cut.lastIndexOf('.');
    return (dot > 120 ? cut.substring(0, dot + 1) : cut).trim();
  }

  String _limitForTranslate(String s, {int maxChars = 900}) =>
      s.length <= maxChars ? s : s.substring(0, maxChars).trim();

  String _formatDiseaseResponse(Map<String, dynamic> result) {
    final prediction = result['prediction'] ?? 'Unknown issue';
    return "Detected: $prediction. Apply basic sanitation, remove heavily infected leaves, improve airflow and drainage. Want a quick treatment plan now?";
  }

  // ===========================================================================
  // Build
  // ===========================================================================

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: appTheme.colorFFF9FA,
      body: SafeArea(
        child: Column(
          children: [
            // Header
            ChatHeader(
              selectedLanguage: _selectedLanguage,
              selectedLanguageName: _selectedLanguageName,
              onLanguageChanged: (entry) {
                setState(() {
                  _selectedLanguage = entry.key;
                  _selectedLanguageName = entry.value;
                });
                _showSnackBar(
                    'Voice language changed to ${entry.value}');
              },
              onLogout: _logout,
              userState: _userLocation?['state'],
              userDistrict: _userLocation?['district'],
            ),

            // Body: Home or Conversation
            if (!_inConversation) ...[
              ChatHomeView(
                userName: _userName,
                userEmail: _userEmail,
                onDiagnoseCrop: _handleImageUpload,
                onCheckPrices: () => _handleQuickAction('rice price'),
                onGovSchemes: () =>
                    _handleQuickAction('government schemes for farmers'),
                onWeatherSoil: () =>
                    _handleQuickAction('weather forecast for farming'),
              ),
            ] else ...[
              _buildConversationView(),
            ],

            // Input bar
            ChatInputBar(
              textController: _textController,
              isLoading: _isLoading,
              isRecording: _isRecording,
              isPlayingResponse: _isPlayingResponse,
              inConversation: _inConversation,
              isDiseaseConversationActive: _isDiseaseConversationActive,
              selectedLanguageName: _selectedLanguageName,
              onSend: _sendMessageHandler,
              onImageUpload: _handleImageUpload,
              onVoiceToggle: _toggleVoiceRecording,
              onNewChat: _resetConversation,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildConversationView() {
    return Expanded(
      child: Container(
        padding: EdgeInsets.all(16.h),
        child: Column(
          children: [
            // Conversation header
            Container(
              padding: EdgeInsets.all(12.h),
              decoration: BoxDecoration(
                color: appTheme.colorFF065F.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12.h),
              ),
              child: Row(
                children: [
                  Icon(
                    _isDiseaseConversationActive ? Icons.healing : Icons.chat,
                    color: appTheme.colorFF065F,
                    size: 16,
                  ),
                  SizedBox(width: 8.h),
                  Text(
                    _isDiseaseConversationActive
                        ? 'Disease Consultation'
                        : 'Agricultural Assistant',
                    style: TextStyleHelper.instance.body14Bold
                        .copyWith(color: appTheme.colorFF065F),
                  ),
                  const Spacer(),
                  GestureDetector(
                    onTap: _resetConversation,
                    child: Container(
                      padding: EdgeInsets.symmetric(
                          horizontal: 8.h, vertical: 4.h),
                      decoration: BoxDecoration(
                        color: appTheme.colorFF065F,
                        borderRadius: BorderRadius.circular(8.h),
                      ),
                      child: Text(
                        'New Chat',
                        style: TextStyleHelper.instance.body12
                            .copyWith(color: appTheme.whiteCustom),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(height: 16.h),

            // Messages list
            Expanded(
              child: ListView.builder(
                controller: _scrollController,
                itemCount: _conversationHistory.length,
                itemBuilder: (context, index) {
                  final msg = _conversationHistory[index];
                  return ChatMessageBubble(
                    message: msg,
                    isDiseaseConversation: _isDiseaseConversationActive,
                    userName: _userName,
                    isPlayingResponse: _isPlayingResponse,
                    onPlayVoice: msg['sender'] == 'bot'
                        ? () => _playResponseAsVoice(msg['text'] ?? '')
                        : null,
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
