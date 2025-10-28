import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../../widgets/language_selector.dart';
import '../../services/translation_service.dart';
import '../../core/app_export.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_image_view.dart';
import '../../services/api_service.dart';
import '../menu_screen/menu_screen.dart';
import '../../services/image_service.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
// ADDED: Authentication imports
import '../../services/auth_service.dart';
import '../auth_screen/login_screen.dart';
// UPDATED: Flutter Sound imports for complete voice integration
import 'package:flutter_sound/flutter_sound.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:path_provider/path_provider.dart';


// Slide transition
class SlideLeftRoute extends PageRouteBuilder {
  final Widget page;
  SlideLeftRoute({required this.page})
      : super(
          pageBuilder: (_, __, ___) => page,
          transitionsBuilder: (_, animation, __, child) => SlideTransition(
            position: Tween<Offset>(begin: const Offset(-1, 0), end: Offset.zero)
                .animate(CurvedAnimation(parent: animation, curve: Curves.easeInOut)),
            child: child,
          ),
          transitionDuration: const Duration(milliseconds: 300),
        );
}


class ChatScreen extends StatefulWidget {
  ChatScreen({Key? key}) : super(key: key);
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}


class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  bool _isLoading = false;

  // ✅ UPDATED: Voice recording with Flutter Sound and Sarvam
  FlutterSoundRecorder? _recorder;
  FlutterSoundPlayer? _player;
  bool _isRecording = false;
  bool _isPlayingResponse = false;
  String? _recordingPath;

  // ✅ ADDED: User authentication state
  String? _userName;
  String? _userEmail;


  // 🔥 Real Chat Session Management
  String? _currentSessionId;
  bool _sessionInitialized = false;
  static const String baseUrl = 'http://10.61.89.244:8000/api'; // 🔥 CHANGE THIS to your server URL


  // Existing conversation state (keep unchanged)
  Map<String, dynamic> _sessionState = {};
  final List<Map<String, String>> _conversationHistory = [];
  bool _inConversation = false;


  // Disease conversation (keep unchanged)
  bool _isDiseaseConversationActive = false;
  String _currentDiseaseContext = "";


  // Language (keep unchanged)
  String _selectedLanguage = 'en-IN';
  String _selectedLanguageName = 'English';


  // ✅ UPDATED: Initialize audio with proper permissions for Flutter Sound
  void _initializeAudio() async {
    _recorder = FlutterSoundRecorder();
    _player = FlutterSoundPlayer();
    
    // Request permissions
    await Permission.microphone.request();
    await Permission.storage.request();
    
    // Initialize recorder and player
    await _recorder!.openRecorder();
    await _player!.openPlayer();
    
    print('🎤 Audio initialized for Sarvam integration');
  }


  // ✅ UPDATED: Complete voice recording with Sarvam STT
  void _toggleVoiceRecording() async {
    if (_isRecording) {
      await _stopRecording();
    } else {
      await _startRecording();
    }
  }

  Future<void> _startRecording() async {
    try {
      setState(() {
        _isRecording = true;
      });
      
      // Get temporary directory for recording
      final directory = await getTemporaryDirectory();
      _recordingPath = '${directory.path}/voice_${DateTime.now().millisecondsSinceEpoch}.wav';
      
      print('🎤 Starting Sarvam voice recording...');
      
      await _recorder!.startRecorder(
        toFile: _recordingPath,
        codec: Codec.pcm16WAV, // ✅ WAV format for Sarvam
        sampleRate: 16000,     // ✅ 16kHz as recommended by Sarvam
      );
      
      // Auto-stop after 30 seconds (Sarvam REST API limit)
      Future.delayed(Duration(seconds: 30), () {
        if (_isRecording) {
          _stopRecording();
        }
      });
      
    } catch (e) {
      print('❌ Recording start error: $e');
      setState(() {
        _isRecording = false;
      });
      _showSnackBar('Failed to start recording');
    }
  }

  Future<void> _stopRecording() async {
    try {
      setState(() {
        _isRecording = false;
      });
      
      print('⏹️ Stopping voice recording...');
      
      await _recorder!.stopRecorder();
      
      if (_recordingPath != null && File(_recordingPath!).existsSync()) {
        print('📁 Audio saved to: $_recordingPath');
        
        // Read audio file as bytes
        final audioFile = File(_recordingPath!);
        final audioBytes = await audioFile.readAsBytes();
        
        print('🎯 Processing with Sarvam STT+Translation...');
        
        // ✅ Use Sarvam STT with automatic translation to English
        final transcript = await TranslationService.speechToTextTranslate(
          audioBytes: audioBytes,
        );
        
        if (transcript != null && transcript.trim().isNotEmpty) {
          print('✅ Voice processed: $transcript');
          
          // Put text in input field and auto-send
          _textController.text = transcript;
          await _sendMessageHandler();
          
        } else {
          print('❌ No speech detected');
          _showSnackBar('No speech detected. Please try again.');
        }
        
        // Clean up audio file
        await audioFile.delete();
      }
    } catch (e) {
      print('❌ Recording stop error: $e');
      _showSnackBar('Error processing voice input');
      setState(() {
        _isRecording = false;
      });
    }
  }

  // ✅ UPDATED: Play AI response using Sarvam TTS with Flutter Sound
  Future<void> _playResponseAsVoice(String text) async {
    try {
      if (_isPlayingResponse || text.trim().isEmpty) return;
      
      setState(() {
        _isPlayingResponse = true;
      });
      
      print('🔊 Converting response to speech with Sarvam...');
      
      // ✅ Use Sarvam TTS
      final audioBytes = await TranslationService.textToSpeech(
        text: text,
        targetLanguageCode: _selectedLanguage,
      );
      
      if (audioBytes != null) {
        // Save audio to temp file
        final tempDir = await getTemporaryDirectory();
        final tempFile = File('${tempDir.path}/response_${DateTime.now().millisecondsSinceEpoch}.wav');
        await tempFile.writeAsBytes(audioBytes);
        
        // Play audio
        await _player!.startPlayer(
          fromURI: tempFile.path,
          whenFinished: () {
            setState(() {
              _isPlayingResponse = false;
            });
            // Clean up temp file
            tempFile.delete();
          },
        );
        
      } else {
        print('❌ TTS failed');
        setState(() {
          _isPlayingResponse = false;
        });
      }
    } catch (e) {
      print('❌ TTS playback error: $e');
      setState(() {
        _isPlayingResponse = false;
      });
    }
  }

  // ✅ ADDED: Helper method for snackbars
  void _showSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: Duration(seconds: 2),
      ),
    );
  }

  // ✅ ADDED: Load user info from AuthService
  void _loadUserInfo() {
    final userInfo = AuthService.userInfo;
    if (userInfo != null) {
      setState(() {
        _userName = userInfo['full_name'] ?? 'User';
        _userEmail = userInfo['email'] ?? '';
      });
    }
  }


  // ✅ ADDED: Logout method
  void _logout() async {
    await AuthService.clearAuthData();
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (context) => LoginScreen()),
    );
  }


  // 🔥 Initialize Chat Session Method
  Future<void> _initializeChatSession() async {
    if (_sessionInitialized) return;


    try {
      print('🔄 Creating chat session...');
      final response = await http.post(
        Uri.parse('$baseUrl/chat/start-session'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({}),
      );


      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['ok'] == true) {
          setState(() {
            _currentSessionId = data['session_id'];
            _sessionInitialized = true;
          });


          print('✅ Session created: $_currentSessionId');


          // Add welcome message to conversation
          _conversationHistory.add({
            'sender': 'bot',
            'text': data['message'] ?? 'Welcome to DigiKisan! How can I help you today?',
            'language': _selectedLanguage,
          });
        }
      }
    } catch (e) {
      print('❌ Session creation error: $e');
      // Continue without session - fallback to existing system
    }
  }

  // ✅ UPDATED: Send Message with Authentication
  Future<void> _sendMessageWithSession(String message) async {
    if (!_sessionInitialized || _currentSessionId == null) {
      _sendMessage(); // Fallback to existing system
      return;
    }


    try {
      print('🗣️ Sending authenticated message: $message');
      
      // ✅ Use AuthService for authenticated requests
      final response = await AuthService.sendChatMessage(message);
      
      if (response != null) {
        final botResponse = response['response'] ?? 'No response received';
        
        // Handle session-based response
        _conversationHistory.add({
          'sender': 'bot',
          'text': botResponse,
          'language': _selectedLanguage,
        });

        // ✅ UPDATED: Auto-play TTS response with new Flutter Sound method
        await _playResponseAsVoice(botResponse);

        print('✅ Authenticated response received');
        return;
      }
    } catch (e) {
      print('❌ Authenticated message error: $e');
    }


    // Fallback to existing system if authenticated message fails
    _sendMessage();
  }


  @override
  void initState() {
    super.initState();
    _loadUserInfo(); // ✅ ADDED: Load user info
    _initializeChatSession();
    _initializeAudio(); // ✅ UPDATED: Initialize audio functionality with Flutter Sound
  }

  // ✅ UPDATED: Dispose method for cleanup
  @override
  void dispose() {
    _textController.dispose();
    _recorder?.closeRecorder();
    _player?.closePlayer();
    super.dispose();
  }


  // -------- Existing Helper Methods (unchanged) --------
  String _stripMarkdown(String s) {
    final noMd = s
        .replaceAll(RegExp(r'[*`#>•\-]+'), '')
        .replaceAll(RegExp(r'\s+\n'), '\n')
        .replaceAll(RegExp(r'\n{2,}'), '\n')
        .replaceAll(RegExp(r' {2,}'), ' ')
        .trim();
    return noMd;
  }


  String _crispify(String s, {int maxChars = 350}) {
    final t = _stripMarkdown(s);
    if (t.length <= maxChars) return t;
    final cut = t.substring(0, maxChars);
    final dot = cut.lastIndexOf('.');
    return (dot > 120 ? cut.substring(0, dot + 1) : cut).trim();
  }


  String _limitForTranslate(String s, {int maxChars = 900}) {
    return s.length <= maxChars ? s : s.substring(0, maxChars).trim();
  }


  // -------- UI Methods --------
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: appTheme.colorFFF9FA,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(context),
            if (!_inConversation) ...[
              _buildUserWelcome(context), // ✅ ADDED: User welcome
              _buildInfoCards(context),
              _buildGreetingSection(context),
              _buildQuickActionChips(context),
              // ✅ REMOVED: Local language selector - using main language selector instead
            ] else ...[
              _buildConversationView(context),
            ],
            _buildInputSection(context),
          ],
        ),
      ),
    );
  }


  // ✅ ADDED: User welcome section
  Widget _buildUserWelcome(BuildContext context) {
    if (_userName == null) return SizedBox.shrink();
    
    return Container(
      margin: EdgeInsets.all(16.h),
      padding: EdgeInsets.all(16.h),
      decoration: BoxDecoration(
        color: appTheme.colorFF065F.withAlpha(20),
        borderRadius: BorderRadius.circular(12.h),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 20.h,
            backgroundColor: appTheme.colorFF065F,
            child: Text(
              _userName!.substring(0, 1).toUpperCase(),
              style: TextStyle(
                color: appTheme.whiteCustom,
                fontSize: 16.fSize,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          SizedBox(width: 12.h),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Welcome back, $_userName!',
                  style: TextStyleHelper.instance.body14Bold,
                ),
                if (_userEmail != null && _userEmail!.isNotEmpty)
                  Text(
                    _userEmail!,
                    style: TextStyleHelper.instance.body12.copyWith(
                      color: appTheme.colorFF6B72,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }


  Widget _buildConversationView(BuildContext context) {
    return Expanded(
      child: Container(
        padding: EdgeInsets.all(16.h),
        child: Column(
          children: [
            Container(
              padding: EdgeInsets.all(12.h),
              decoration: BoxDecoration(
                color: appTheme.colorFF065F.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12.h),
              ),
              child: Row(
                children: [
                  Icon(_isDiseaseConversationActive ? Icons.healing : Icons.chat,
                      color: appTheme.colorFF065F, size: 16),
                  SizedBox(width: 8.h),
                  Text(
                    _isDiseaseConversationActive ? 'Disease Consultation' : 'Agricultural Assistant',
                    style: TextStyleHelper.instance.body14Bold.copyWith(color: appTheme.colorFF065F),
                  ),
                  const Spacer(),
                  GestureDetector(
                    onTap: _resetConversation,
                    child: Container(
                      padding: EdgeInsets.symmetric(horizontal: 8.h, vertical: 4.h),
                      decoration: BoxDecoration(
                        color: appTheme.colorFF065F,
                        borderRadius: BorderRadius.circular(8.h),
                      ),
                      child: Text('New Chat',
                          style: TextStyleHelper.instance.body12.copyWith(color: appTheme.whiteCustom)),
                    ),
                  ),
                ],
              ),
            ),
            SizedBox(height: 16.h),


            // Messages
            Expanded(
              child: ListView.builder(
                itemCount: _conversationHistory.length,
                itemBuilder: (context, index) {
                  final message = _conversationHistory[index];
                  final isUser = message['sender'] == 'user';

                  return Container(
                    margin: EdgeInsets.only(bottom: 12.h),
                    child: Row(
                      mainAxisAlignment:
                          isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (!isUser) ...[
                          CircleAvatar(
                            radius: 16.h,
                            backgroundColor: appTheme.colorFF065F,
                            child: Icon(_isDiseaseConversationActive ? Icons.healing : Icons.eco,
                                color: appTheme.whiteCustom, size: 16),
                          ),
                          SizedBox(width: 8.h),
                        ],
                        ConstrainedBox(
                          constraints: BoxConstraints(
                            maxWidth: MediaQuery.of(context).size.width * 0.78,
                          ),
                          child: Container(
                            padding: EdgeInsets.symmetric(horizontal: 12.h, vertical: 8.h),
                            decoration: BoxDecoration(
                              color: isUser ? appTheme.colorFF065F : appTheme.whiteCustom,
                              borderRadius: BorderRadius.circular(12.h),
                              border: isUser
                                  ? null
                                  : Border.all(color: appTheme.colorFF10B9, width: 1.h),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (message['image_path'] != null) ...[
                                  Container(
                                    margin: EdgeInsets.only(bottom: 8.h),
                                    child: ClipRRect(
                                      borderRadius: BorderRadius.circular(8.h),
                                      child: message['image_bytes'] != null
                                          ? Image.memory(
                                              base64Decode(message['image_bytes']!),
                                              width: 200.w,
                                              height: 150.h,
                                              fit: BoxFit.cover,
                                            )
                                          : FutureBuilder<Uint8List>(
                                              future: ImageService.getImageBytes(
                                                  message['image_path']!),
                                              builder: (context, snapshot) {
                                                if (snapshot.connectionState ==
                                                        ConnectionState.done &&
                                                    snapshot.hasData &&
                                                    snapshot.data!.isNotEmpty) {
                                                  return Image.memory(snapshot.data!,
                                                      width: 200.w,
                                                      height: 150.h,
                                                      fit: BoxFit.cover);
                                                }
                                                return Container(
                                                  width: 200.w,
                                                  height: 150.h,
                                                  decoration: BoxDecoration(
                                                    color: Colors.grey.shade200,
                                                    borderRadius: BorderRadius.circular(8.h),
                                                  ),
                                                  child: const Center(
                                                      child: Icon(Icons.image_not_supported)),
                                                );
                                              },
                                            ),
                                    ),
                                  ),
                                ],
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        message['text'] ?? '',
                                        softWrap: true,
                                        textAlign: TextAlign.left,
                                        style: TextStyleHelper.instance.body14.copyWith(
                                          color:
                                              isUser ? appTheme.whiteCustom : appTheme.blackCustom,
                                        ),
                                      ),
                                    ),
                                    // ✅ UPDATED: Voice playback button for bot messages with Flutter Sound
                                    if (!isUser && message['text'] != null) ...[
                                      SizedBox(width: 8.h),
                                      GestureDetector(
                                        onTap: () => _playResponseAsVoice(message['text']!),
                                        child: Container(
                                          padding: EdgeInsets.all(4.h),
                                          decoration: BoxDecoration(
                                            color: _isPlayingResponse 
                                                ? appTheme.colorFF065F 
                                                : appTheme.colorFF065F.withAlpha(50),
                                            borderRadius: BorderRadius.circular(4.h),
                                          ),
                                          child: Icon(
                                            _isPlayingResponse ? Icons.pause : Icons.volume_up,
                                            color: _isPlayingResponse 
                                                ? appTheme.whiteCustom 
                                                : appTheme.colorFF065F,
                                            size: 12.h,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                        if (isUser) ...[
                          SizedBox(width: 8.h),
                          CircleAvatar(
                            radius: 16.h,
                            backgroundColor: appTheme.colorFFF3F4,
                            child: _userName != null 
                                ? Text(
                                    _userName!.substring(0, 1).toUpperCase(),
                                    style: TextStyle(
                                      color: appTheme.colorFF065F,
                                      fontSize: 12.fSize,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  )
                                : Icon(Icons.person, color: appTheme.colorFF065F, size: 16),
                          ),
                        ],
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }


  void _resetConversation() {
    setState(() {
      _inConversation = false;
      _conversationHistory.clear();
      _sessionState = {}; // 🔥 CRITICAL: Reset session state
      _isDiseaseConversationActive = false;
      _currentDiseaseContext = "";
    });
    
    // Reinitialize session on reset
    _sessionInitialized = false;
    _currentSessionId = null;
    _initializeChatSession();
  }

  // ✅ UPDATED: Header with logout functionality
  Widget _buildHeader(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: appTheme.whiteCustom,
        boxShadow: [
          BoxShadow(
            color: appTheme.blackCustom.withAlpha(26),
            blurRadius: 10.h,
            offset: Offset(0, 2.h),
          ),
        ],
        border: Border(
          bottom: BorderSide(color: appTheme.colorFFF3F4, width: 1.h),
        ),
      ),
      padding: EdgeInsets.symmetric(horizontal: 16.h, vertical: 16.h),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          CustomButton(
            variant: CustomButtonVariant.icon,
            iconPath: ImageConstant.imgButtonBlueGray900,
            width: 40.h,
            height: 40.h,
            borderColor: appTheme.colorFF1F29,
            borderRadius: 12.h,
            onPressed: () {
              Navigator.of(context).push(SlideLeftRoute(page: MenuScreen()));
            },
          ),
          Row(
            children: [
              CustomImageView(
                imagePath: ImageConstant.imgSproutGraphic1,
                height: 16.h,
                width: 16.h,
              ),
              SizedBox(width: 8.h),
              Text('DigiKisan', style: TextStyleHelper.instance.title18Bold),
            ],
          ),
          Row(
            children: [
              LanguageSelector(
                selectedLanguage: _selectedLanguage,
                selectedLanguageName: _selectedLanguageName,
                onLanguageChanged: (code, name) {
                  setState(() {
                    _selectedLanguage = code;
                    _selectedLanguageName = name;
                  });
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Voice language changed to $name'), duration: const Duration(seconds: 2)),
                  );
                },
              ),
              SizedBox(width: 8.h),
              // ✅ ADDED: Logout button
              PopupMenuButton<String>(
                icon: Icon(Icons.more_vert, color: appTheme.colorFF065F),
                onSelected: (value) {
                  if (value == 'logout') {
                    _logout();
                  }
                },
                itemBuilder: (context) => [
                  PopupMenuItem(
                    value: 'logout',
                    child: Row(
                      children: [
                        Icon(Icons.logout, color: appTheme.colorFF065F),
                        SizedBox(width: 8.h),
                        Text('Logout'),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfoCards(BuildContext context) { 
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: 16.h, vertical: 24.h),
      child: Row(
        children: [
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: appTheme.whiteCustom,
                borderRadius: BorderRadius.circular(12.h),
                border: Border.all(color: appTheme.colorFF10B9, width: 1.h),
                boxShadow: [
                  BoxShadow(
                    color: appTheme.blackCustom.withAlpha(26),
                    blurRadius: 10.h,
                    offset: Offset(0, 2.h),
                  ),
                ],
              ),
              padding: EdgeInsets.all(16.h),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                    Text('📍Nagpur', style: TextStyleHelper.instance.body12),
                    CustomImageView(imagePath: ImageConstant.imgSun, height: 24.h, width: 24.h),
                  ]),
                  SizedBox(height: 12.h),
                  Row(children: [
                    Text('30°C', style: TextStyleHelper.instance.body14Bold),
                    SizedBox(width: 8.h),
                    Text('Sunny', style: TextStyleHelper.instance.body12),
                  ]),
                ],
              ),
            ),
          ),
          SizedBox(width: 16.h),
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: appTheme.whiteCustom,
                borderRadius: BorderRadius.circular(12.h),
                border: Border.all(color: appTheme.colorFF10B9, width: 1.h),
                boxShadow: [
                  BoxShadow(
                    color: appTheme.blackCustom.withAlpha(26),
                    blurRadius: 10.h,
                    offset: Offset(0, 2.h),
                  ),
                ],
              ),
              padding: EdgeInsets.all(16.h),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                    Text('🥔 Potato', style: TextStyleHelper.instance.body12),
                    CustomImageView(imagePath: ImageConstant.imgCurrencycircledollar, height: 24.h, width: 24.h),
                  ]),
                  SizedBox(height: 12.h),
                  Row(children: [
                    Text('₹2250', style: TextStyleHelper.instance.body14Bold),
                    SizedBox(width: 8.h),
                    Text('/quintal', style: TextStyleHelper.instance.body12),
                  ]),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }


  Widget _buildGreetingSection(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: 16.h, vertical: 32.h),
      child: Text(
        _userName != null 
            ? 'Hello $_userName!\nHow can I help your farm today?'
            : 'Hello!\nHow can I help your farm today?',
        textAlign: TextAlign.center,
        style: TextStyleHelper.instance.title16SemiBold.copyWith(height: 1.5),
      ),
    );
  }


  Widget _buildQuickActionChips(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: 16.h),
      child: GridView.count(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        crossAxisCount: 2,
        crossAxisSpacing: 12.h,
        mainAxisSpacing: 12.h,
        childAspectRatio: 2.5,
        children: [
          _buildQuickActionChip(
            context: context,
            iconPath: ImageConstant.imgMenuCamera,
            text: 'Diagnose Crop Disease',
            onPressed: () => _handleImageUpload(),
          ),
          _buildQuickActionChip(
            context: context,
            iconPath: ImageConstant.imgPrices,
            text: 'Check Crop Prices',
            onPressed: () => _handleQuickAction('rice price'),
          ),
          _buildQuickActionChip(
            context: context,
            iconPath: ImageConstant.imgMenuCamera,
            text: 'Government Schemes',
            onPressed: () => _handleQuickAction('government schemes for farmers'),
          ),
          _buildQuickActionChip(
            context: context,
            iconPath: ImageConstant.imgMenuWeather,
            text: 'Weather and Soil',
            onPressed: () => _handleQuickAction('weather forecast for farming'),
          ),
        ],
      ),
    );
  }


  void _handleQuickAction(String message) {
    _textController.text = message;
    _sendMessageHandler();
  }


  Widget _buildQuickActionChip({
    required BuildContext context,
    required String iconPath,
    required String text,
    required VoidCallback onPressed,
  }) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        decoration: BoxDecoration(
          color: appTheme.whiteCustom,
          borderRadius: BorderRadius.circular(16.h),
          border: Border.all(color: appTheme.blackCustom.withValues(alpha: 0.1), width: 1.h),
          boxShadow: [BoxShadow(color: appTheme.blackCustom.withAlpha(13), blurRadius: 4.h, offset: Offset(0, 1.h))],
        ),
        padding: EdgeInsets.symmetric(horizontal: 12.h, vertical: 8.h),
        child: Row(
          children: [
            CustomImageView(imagePath: iconPath, height: 16.h, width: 16.h, color: appTheme.colorFF065F),
            SizedBox(width: 8.h),
            Expanded(child: Text(text, style: TextStyleHelper.instance.chipText, maxLines: 2, overflow: TextOverflow.ellipsis)),
          ],
        ),
      ),
    );
  }

  // Image upload (unchanged)
  void _handleImageUpload() async {
    try {
      setState(() => _isLoading = true);


      final XFile? selectedImage = await ImageService.showImageSourceDialog(context);
      if (selectedImage == null) return;


      final imageBytes = await selectedImage.readAsBytes();
      _conversationHistory.add({
        'sender': 'user',
        'text': '📸 Uploaded crop image for diagnosis',
        'language': _selectedLanguage,
        'image_path': selectedImage.path,
        'image_bytes': base64Encode(imageBytes),
      });


      print('🔄 Analyzing crop image...');
      
      final result = await ImageService.uploadForDiseaseDetection(selectedImage);


      if (result['conversation_started'] == true && result['prediction'] != null) {
        setState(() {
          _isDiseaseConversationActive = true;
          _currentDiseaseContext = result['prediction'];
          _inConversation = true;
        });
      }


      final raw = (result['ai_summary'] as String?) ?? _formatDiseaseResponse(result);
      final crisp = _crispify(raw);
      final toTranslate = _limitForTranslate(crisp, maxChars: 900);


      String reply = toTranslate;
      if (_selectedLanguage != 'en-IN') {
        reply = await TranslationService.translateText(toTranslate, 'en-IN', _selectedLanguage);
      }


      _conversationHistory.add({'sender': 'bot', 'text': reply, 'language': _selectedLanguage});
      
      // ✅ UPDATED: Auto-play TTS for image analysis result with Flutter Sound
      await _playResponseAsVoice(reply);
      
    } catch (e) {
      print('❌ Image upload error: $e');
      _conversationHistory.add({
        'sender': 'bot',
        'text': "Couldn't analyze the image. Please try again with a clear photo.",
        'language': _selectedLanguage,
      });
    } finally {
      setState(() => _isLoading = false);
    }
  }


  String _formatDiseaseResponse(Map<String, dynamic> result) {
    final prediction = result['prediction'] ?? 'Unknown issue';
    return "Detected: $prediction. Apply basic sanitation, remove heavily infected leaves, improve airflow and drainage. Want a quick treatment plan now?";
  }


  Future<String> _sendDiseaseChat(String message, String diseaseContext) async {
    try {
      final res = await ApiService.sendDiseaseChat(message, diseaseContext);
      if (res['ok'] == true) {
        final raw = res['response'] as String;
        return _crispify(raw);
      } else {
        throw Exception(res['error'] ?? 'Disease chat API error');
      }
    } catch (e) {
      print('❌ Disease chat error: $e');
      rethrow;
    }
  }


  // ✅ UPDATED: Send Message Handler with Step 4 changes for TTS auto-play
  Future<void> _sendMessageHandler() async {
    final message = _textController.text.trim();
    if (message.isEmpty) return;


    setState(() {
      _isLoading = true;
      _inConversation = true;
    });


    _conversationHistory.add({'sender': 'user', 'text': message, 'language': _selectedLanguage});
    print('🗣️ User message: $message ($_selectedLanguageName)');


    try {
      String englishMessage = message;
      if (_selectedLanguage != 'en-IN') {
        englishMessage = await TranslationService.translateText(message, _selectedLanguage, 'en-IN');
        englishMessage = englishMessage.trim().replaceAll(RegExp(r'[.,;!]+$'), '');
      }

      // ✅ Try authenticated messaging first
      if (AuthService.token != null) {
        await _sendMessageWithSession(englishMessage);
        _textController.clear();
        setState(() => _isLoading = false);
        return;
      }


      // Fallback to existing logic if no authentication (unchanged)
      String botResponse = '';


      if (_isDiseaseConversationActive && _currentDiseaseContext.isNotEmpty) {
        try {
          final concise = await _sendDiseaseChat(englishMessage, _currentDiseaseContext);
          botResponse = concise;
        } catch (_) {
          _isDiseaseConversationActive = false;
          _currentDiseaseContext = "";
        }
      }


      if (botResponse.isEmpty) {
        if (_sessionState.isNotEmpty && _sessionState['in_slot_fill'] == true) {
          final result = await ApiService.chatWithSlots(englishMessage, _sessionState);
          botResponse = _crispify(result['response'] ?? '');
          _sessionState = result['session_state'] ?? {};
          if (result['completed'] == true) {
            _sessionState = {};
            botResponse += "\nAnything else?";
          }
        } else {
          final classification = await ApiService.classifyText(englishMessage);
          final intent = classification['result']['prediction'];
          if (intent == 'price_enquiry') {
            final result = await ApiService.chatWithSlots(englishMessage, _sessionState);
            botResponse = _crispify(result['response'] ?? '');
            _sessionState = result['session_state'] ?? {};
          } else {
            botResponse = "Hi! Ask for crop prices, quick disease help, or weather. What do you need?";
          }
        }
      }


      // Translate concise text, enforcing limit
      String display = botResponse;
      if (_selectedLanguage != 'en-IN') {
        display = await TranslationService.translateText(
          _limitForTranslate(botResponse, maxChars: 900),
          'en-IN',
          _selectedLanguage,
        );
      }


      _conversationHistory.add({'sender': 'bot', 'text': display, 'language': _selectedLanguage});
      
      // ✅ UPDATED: Step 4 - AUTO-PLAY AI response as voice with Flutter Sound
      await _playResponseAsVoice(display);
      
      _textController.clear();
    } catch (e) {
      print('❌ API Error: $e');
      String errorMsg = "Having connection trouble. Please try again, or restart the app.";
      if (_selectedLanguage != 'en-IN') {
        try {
          errorMsg = await TranslationService.translateText(errorMsg, 'en-IN', _selectedLanguage);
        } catch (_) {}
      }
      _conversationHistory.add({'sender': 'bot', 'text': errorMsg, 'language': _selectedLanguage});
    }


    setState(() => _isLoading = false);
  }


  // Keep existing _sendMessage for backward compatibility
  void _sendMessage() => _sendMessageHandler();


  // ✅ UPDATED: Input section with Flutter Sound voice integration
  Widget _buildInputSection(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: appTheme.whiteCustom,
        borderRadius: BorderRadius.only(topLeft: Radius.circular(24.h), topRight: Radius.circular(24.h)),
        boxShadow: [BoxShadow(color: appTheme.blackCustom.withAlpha(26), blurRadius: 10.h, offset: Offset(0, -2.h))],
        border: Border(top: BorderSide(color: appTheme.colorFFF3F4, width: 1.h)),
      ),
      padding: EdgeInsets.all(16.h),
      child: Column(
        children: [
          TextField(
            controller: _textController,
            decoration: InputDecoration(
              hintText: _isRecording 
                  ? "🎤 Recording in ${_selectedLanguageName}..." 
                  : _isLoading
                      ? 'Thinking...'
                      : _isDiseaseConversationActive
                          ? 'Ask about treatment, prevention, next steps...'
                          : _inConversation
                              ? 'Ask anything about farming...'
                              : 'Ask about crop prices, diseases, weather...',
              hintStyle: TextStyleHelper.instance.body14.copyWith(
                color: _isRecording ? appTheme.colorFF065F : appTheme.colorFF6B72,
              ),
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              contentPadding: EdgeInsets.zero,
              suffixIcon: _isLoading
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : null,
            ),
            style: TextStyleHelper.instance.body14,
            onSubmitted: (_) => _sendMessageHandler(),
            maxLines: 3,
            minLines: 1,
          ),
          SizedBox(height: 16.h),
          
          // ✅ UPDATED: Buttons row with Flutter Sound mic button
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(children: [
                if (_inConversation) ...[
                  CustomButton(
                    variant: CustomButtonVariant.filled,
                    text: 'New Chat',
                    backgroundColor: appTheme.colorFF6B72,
                    textColor: appTheme.whiteCustom,
                    borderRadius: 12.h,
                    fontSize: 12.fSize,
                    fontWeight: FontWeight.w400,
                    padding: EdgeInsets.symmetric(horizontal: 12.h, vertical: 6.h),
                    onPressed: _resetConversation,
                  ),
                  SizedBox(width: 8.h),
                ],
                CustomButton(
                  variant: CustomButtonVariant.icon,
                  iconPath: ImageConstant.imgButtonBlueGray90001,
                  width: 28.h,
                  height: 28.h,
                  borderColor: appTheme.blackCustom,
                  borderRadius: 12.h,
                  onPressed: _handleImageUpload,
                ),
                SizedBox(width: 8.h),
                
                // ✅ UPDATED: MIC BUTTON with Flutter Sound recording
                GestureDetector(
                  onTap: _toggleVoiceRecording,
                  child: Container(
                    width: 28.h,
                    height: 28.h,
                    decoration: BoxDecoration(
                      color: _isRecording ? appTheme.colorFF065F : appTheme.whiteCustom,
                      borderRadius: BorderRadius.circular(12.h),
                      border: Border.all(
                        color: _isRecording ? appTheme.colorFF065F : appTheme.blackCustom,
                        width: 1.h,
                      ),
                    ),
                    child: Icon(
                      _isRecording ? Icons.stop : Icons.mic,
                      color: _isRecording ? appTheme.whiteCustom : appTheme.colorFF065F,
                      size: 16.h,
                    ),
                  ),
                ),
                SizedBox(width: 8.h),
                
                CustomButton(
                  variant: CustomButtonVariant.icon,
                  iconPath: ImageConstant.imgButtonBlueGray9000128x28,
                  width: 28.h,
                  height: 28.h,
                  borderColor: appTheme.blackCustom,
                  borderRadius: 12.h,
                  onPressed: () => print('File attachment opened'),
                ),
              ]),
              
              CustomButton(
                variant: CustomButtonVariant.filled,
                text: _isLoading ? 'Thinking...' : 'Send',
                backgroundColor: _isLoading ? appTheme.colorFF6B72 : appTheme.colorFF065F,
                textColor: appTheme.whiteCustom,
                borderRadius: 12.h,
                fontSize: 14.fSize,
                fontWeight: FontWeight.w500,
                padding: EdgeInsets.symmetric(horizontal: 20.h, vertical: 8.h),
                onPressed: _isLoading ? null : _sendMessageHandler,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
