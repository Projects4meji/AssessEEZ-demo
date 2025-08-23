<?php

namespace App\Http\Helpers;

use App\Models\JobsLogs;
use Carbon\Carbon;
use Carbon\CarbonPeriod;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Str;
use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;
use App\Models\User;
use App\Models\ScoreLogs;
use App\Http\Helpers\ExpoNotifications\ExpoMessage;
use App\Http\Helpers\ExpoNotifications\Expo;
use App\Mail\CreateUserMail;
use App\Mail\EmailChangeMail;
use App\Mail\OtpMail;
use App\Models\BlockEntity;
use App\Models\BusinessDays;
use App\Models\Businesses_Offers;
use App\Models\BusinessHours;
use App\Models\Category;
// use DB;
use App\Models\Notifications;
use App\Models\City_States;
use App\Models\CH_Message;
use App\Models\CompanyRealtor;
use App\Models\Customer;
use App\Models\Document;
use App\Models\EventLog;
use App\Models\Follower;
use App\Models\Initiative;
use App\Models\InitiativePost;
use App\Models\Invoice;
use App\Models\InvoiceDetail;
use App\Models\Listing;
use App\Models\Notification;
use App\Models\Otp;
use App\Models\PasswordResetToken;
use App\Models\PostComment;
use App\Models\PostImpression;
use App\Models\ProfilePicture;
use App\Models\PropertyHistory;
use App\Models\RequestModel;
use App\Models\SavedProperty;
use App\Models\UserNotificationPreference;
use App\Models\UserQualification;
use GuzzleHttp\Client;
use GuzzleHttp\Psr7\Request;
use Illuminate\Support\Facades\App;
use Mockery\Undefined;

use Illuminate\Support\Facades\DB;
use PHPMailer\PHPMailer\SMTP;
use Illuminate\Support\Facades\URL;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;
use MailchimpMarketing\ApiClient;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Log;

class Helper
{

    public static function getCompanyAdminId($id)
    {
        $selectResource = User::where('id', $id)->first();

        $companyAdminId = 0;
        if($selectResource != null) {
            $selectUser = User::where('customer_id', $selectResource->customer_id)
            ->where('role_id', '2')->first();
            
            if($selectUser != null) {
                $companyAdminId = $selectUser->id;
            }
        }

        return (int)$companyAdminId;
    }

    public static function getAdmin_ids($id)
    {
        $companyId = Helper::getCompanyAdminId($id);
        $adminIds = User::where('role_id', 6)->where('created_by', $companyId)->pluck('id');

        $adminIds[] = $companyId;

        return $adminIds;
    }    

    public static function getCompanyLogo($id)
    {
        $selectResource = User::where('id', $id)->first();
        $avatar = null;

        if (($selectResource == null) || ($selectResource->avatar == 'placeholder.png')  || ($selectResource->avatar == null)) {
            // $avatar = URL::to('/') . Storage::disk('local')->url('public/user_avatar/avatar.png');
            $avatar = env('AWS_URL') . "/avatar.png";
            
        } else {
            // $avatar = URL::to('/') . Storage::disk('local')->url('public/user_avatar/' . $selectResource->avatar);
            $avatar = env('AWS_URL') . '/customer/' . $selectResource->customer_id . '/user_avatar/' . $selectResource->avatar;
        }

        return $avatar;
    }

    public static function getUserInfo($id)
    {
        $selectResource = User::where('id', $id)->first();
        return $selectResource;
    }

    public static function getRoleId($id)
    {
        $selectRole = User::where('id', $id)->first();

        return (int)$selectRole->role_id;
    }

    public static function sendOtp($data)
    {
        $otp = random_int(100000, 999999);
        $verification_method = $data['verification_method'];

        Otp::updateOrCreate(
            ['email' => $data['email']],
            ['otp' => $otp]
        );

        if ($verification_method == 1) {
            $client = new Client();
            $response = $client->request('GET', 'https://app.notify.lk/api/v1/send', [
                'query' => [
                    'user_id' => '27382',
                    'api_key' => 'cOnVFx07A8K8Vrki3kwf',
                    'sender_id' => 'NotifyDEMO',
                    'to' => (int)$data['email'],
                    'message' => 'Your OTP code is: ' . $otp,
                ]
            ]);
        } else {
            Mail::to($data['email'])->send(new OtpMail($otp));
        }

        return true;
    }

    public static function sendForgotPassword($data)
    {
        $otp = random_int(100000, 999999);
        $verification_method = $data['verification_method'];

        PasswordResetToken::updateOrCreate(
            ['email' => $data['email']],
            ['otp' => $otp]
        );

        if ($verification_method == 1) {
            $client = new Client();
            $response = $client->request('GET', 'https://app.notify.lk/api/v1/send', [
                'query' => [
                    'user_id' => '27382',
                    'api_key' => 'cOnVFx07A8K8Vrki3kwf',
                    'sender_id' => 'NotifyDEMO',
                    'to' => (int)$data['email'],
                    'message' => 'Your OTP code is: ' . $otp,
                ]
            ]);
        } else {
            Mail::to($data['email'])->send(new OtpMail($otp));
        }

        return true;
    }

    public static function sendEmailChange($data)
    {
        $otp = random_int(100000, 999999);
        $verification_method = $data['verification_method'];

        Otp::updateOrCreate(
            ['email' => $data['email']],
            ['otp' => $otp]
        );

        if ($verification_method == 1) {
            $client = new Client();
            $response = $client->request('GET', 'https://app.notify.lk/api/v1/send', [
                'query' => [
                    'user_id' => '27382',
                    'api_key' => 'cOnVFx07A8K8Vrki3kwf',
                    'sender_id' => 'NotifyDEMO',
                    'to' => (int)$data['email'],
                    'message' => 'Your OTP code is: ' . $otp,
                ]
            ]);
        } else {
            Mail::to($data['email'])->send(new EmailChangeMail($otp));
        }

        return true;
    }

    public static function createUserCredentials($data)
    {
        $email = $data['email'];
        $password = $data['password'];
        $role = "";
        $institute = $data['institute'];
        $qualification = $data['qualification'];
        
        switch((int)$data['role']) {            
            case 2:
            case 6:
                $role = 'You havs been registered as Admin by ' . $institute;
                break;
            case 3:
                $role = 'You have been registered as Learner in (' . $qualification . ') by ' . $institute;
                break;
            case 4:
                $role = 'You have been registered as Assessor in (' . $qualification . ') by ' . $institute;
                break;
            case 5:
                $role = 'You have been registered as IQA in (' . $qualification . ') by ' . $institute;
                break;
            case 7:
                $role = 'You have been registered as EQA in (' . $qualification . ') by ' . $institute;
                break;
        }        

        Mail::to($data['email'])->send(new CreateUserMail($email, $password, $role));
        return true;
    }

    public static function searchCategory($search_data)
    {
        $categories = Category::with('parent')->where('name', 'like', "%$search_data%")->get();

        $findTopParent = function ($category) use (&$findTopParent) {
            while ($category && $category->parent) {
                $category = $category->parent;
            }
            return $category;
        };

        $topParentIds = $categories->map(function ($category) use ($findTopParent) {
            $topParent = $findTopParent($category);
            return $topParent ? $topParent->id : null;
        })->filter()->unique();

        return $topParentIds;
    }

    public static function getLastcode()
    {
        // Fetch the last user's code and increment it
        $lastUser = User::orderBy('id', 'desc')->first();
        $lastCode = $lastUser ? intval($lastUser->code) : 0;
        $newCode = str_pad($lastCode + 1, 5, '0', STR_PAD_LEFT);
        return $newCode;
    }

    public static function generateInvoicePDF($data)
    {
        $invoice = Invoice::where('invoice_no', $data['invoice_no'])->first();
        if ($invoice) {
            $customer = Customer::where('id', $invoice->customer_id)->first();
            $price = $customer ? $customer->price : 0;
            $vat = $customer ? $customer->vat : false;
            $customer_name = $customer ? $customer->name : 'N/A';
            $customer_address = $customer ? $customer->address : 'N/A';
            $invoice_no = $invoice->invoice_no;

            $invoice_details = InvoiceDetail::where('invoice_no', $data['invoice_no'])
                // ->join('user_qualifications', 'invoice_details.learner_id', '=', 'user_qualifications.id')                
                ->join('user_qualifications', function($join) {
                  $join->on('invoice_details.learner_id', '=', 'user_qualifications.user_id');
                  $join->on('invoice_details.qualification_id', '=', 'user_qualifications.qualification_id');
                })->join('qualifications', 'invoice_details.qualification_id', '=', 'qualifications.id')
                ->select('user_qualifications.first_name', 'user_qualifications.middle_name', 'user_qualifications.sur_name', 'qualifications.sub_title as qualification_title')
                ->get()
                ->toArray(); // convert to array for easier use in the view

            $totalfee = ($price * count($invoice_details));
            $vat_charged = ($vat ? (($totalfee / 100) * 20) : 0);
            $total = ($totalfee + $vat_charged);
            // $dueDate = $customer->created_at->addDays($customer->payment_terms);
            $terms = $customer->payment_terms;
            $dueDate = $customer->created_at->addDays((int)$terms)->format('Y-m-d');

            return [
                'customer_name' => $customer_name,
                'customer_address' => $customer_address,
                'invoice_no' => $invoice_no,
                'invoice_details' => $invoice_details,
                'service_fee' => $totalfee,
                'vat' => $vat_charged,
                'total' => $total,
                'payment_due' => $dueDate,
            ];
        } else {
            return 'Data not found!';
        }
    }








    public static $enc_check = false;

    // public static function sendforgotpassword($data, $code)
    // {
    //     $email_a = trim($data['email']);

    //     $mail = new PHPMailer(true);

    //     $url = URL::to('/') . '/reset_password_link/' . $data['email'] . '/' . $code;

    //     try {
    //         //Server settings
    //         // $mail->SMTPDebug = SMTP::DEBUG_SERVER;                      // Enable verbose debug output
    //         $mail->isSMTP(); // Send using SMTP
    //         $mail->Host = env('MAIL_HOST'); // Set the SMTP server to send through
    //         $mail->SMTPAuth = true; // Enable SMTP authentication
    //         $mail->Username = env('mail_username'); // SMTP username
    //         $mail->Password = env('MAIL_PASSWORD'); // SMTP password
    //         $mail->SMTPSecure = env('MAIL_ENCRYPTION'); // Enable TLS encryption; `PHPMailer::ENCRYPTION_SMTPS` also accepted
    //         $mail->Port = env('MAIL_PORT'); // TCP port to connect to

    //         $mail->SMTPOptions = [
    //             'ssl' => [
    //                 'verify_peer' => false,
    //                 'verify_peer_name' => false,
    //                 'allow_self_signed' => true,
    //             ],
    //         ];

    //         //Recipients
    //         $mail->setFrom(
    //             env('mail_username'),
    //             env('MAIL_FROM_NAME')
    //         );
    //         //  $mail->addAddress($email_a, $user->fname  );     // Add a recipient
    //         $mail->addAddress($email_a, $data['email']); // Add a recipient

    //         // Content
    //         $mail->isHTML(true); // Set email format to HTML
    //         $mail->Subject = 'Password Reset request';
    //         // $mail->Subject = "Hello " . $data['email'] . " Recieved a video link!";

    //         $mail->Body =
    //             "
    //        <p>Hi  " .
    //             $data['firstname'] .
    //             ' ' .
    //             $data['lastname'] .
    //             ",</p>
    //        <p>We received a request to reset your password. Your otp code is </p> " . $code . "
    //        <p>If you didn't request a new password, Secure your account by changing your password.</p>
    //        </br>
    //        <p>Regards, </p>
    //        <p> " . env('MAIL_FROM_NAME') . "</p>";

    //         $mail->send();
    //         return true;
    //     } catch (Exception $e) {
    //         dd($e);
    //         return $e;
    //     }
    // }

    public static function sendverificationemail($data, $code)
    {
        $email_a = trim($data['email']);

        $mail = new PHPMailer(true);

        $url = URL::to('/') . '/reset_password_link/' . $data['email'] . '/' . $code;

        try {
            //Server settings
            // $mail->SMTPDebug = SMTP::DEBUG_SERVER;                      // Enable verbose debug output
            $mail->isSMTP(); // Send using SMTP
            $mail->Host = env('MAIL_HOST'); // Set the SMTP server to send through
            $mail->SMTPAuth = true; // Enable SMTP authentication
            $mail->Username = env('mail_username'); // SMTP username
            $mail->Password = env('MAIL_PASSWORD'); // SMTP password
            $mail->SMTPSecure = env('MAIL_ENCRYPTION'); // Enable TLS encryption; `PHPMailer::ENCRYPTION_SMTPS` also accepted
            $mail->Port = env('MAIL_PORT'); // TCP port to connect to

            $mail->SMTPOptions = [
                'ssl' => [
                    'verify_peer' => false,
                    'verify_peer_name' => false,
                    'allow_self_signed' => true,
                ],
            ];

            //Recipients
            $mail->setFrom(
                env('mail_username'),
                env('MAIL_FROM_NAME')
            );
            //  $mail->addAddress($email_a, $user->fname  );     // Add a recipient
            $mail->addAddress($email_a, $data['email']); // Add a recipient

            // Content
            $mail->isHTML(true); // Set email format to HTML
            $mail->Subject = 'Two Factor Verification';
            // $mail->Subject = "Hello " . $data['email'] . " Recieved a video link!";

            $mail->Body =
                "
           <p>Hi  " .
                $data['firstname'] .
                ' ' .
                $data['lastname'] .
                ",</p>
           <p>we have sent you an email by two factor verification. Your verification code is </p> " . $code . "           
           </br>
           <p>Regards, </p>
           <p> " . env('MAIL_FROM_NAME') . "</p>";

            $mail->send();
            return true;
        } catch (Exception $e) {
            return false;
        }
    }

    public static function sendchangepassword($data)
    {
        $email_a = trim($data['email']);

        $mail = new PHPMailer(true);

        try {
            //Server settings
            // $mail->SMTPDebug = SMTP::DEBUG_SERVER;                      // Enable verbose debug output
            $mail->isSMTP(); // Send using SMTP
            $mail->Host = env('MAIL_HOST'); // Set the SMTP server to send through
            $mail->SMTPAuth = true; // Enable SMTP authentication
            $mail->Username = env('mail_username'); // SMTP username
            $mail->Password = env('MAIL_PASSWORD'); // SMTP password
            $mail->SMTPSecure = env('MAIL_ENCRYPTION'); // Enable TLS encryption; `PHPMailer::ENCRYPTION_SMTPS` also accepted
            $mail->Port = env('MAIL_PORT'); // TCP port to connect to

            $mail->SMTPOptions = [
                'ssl' => [
                    'verify_peer' => false,
                    'verify_peer_name' => false,
                    'allow_self_signed' => true,
                ],
            ];

            //Recipients
            $mail->setFrom(
                env('mail_username'),
                env('MAIL_FROM_NAME')
            );


            //  $mail->addAddress($email_a, $user->fname  );     // Add a recipient
            $mail->addAddress($email_a, $data['email']); // Add a recipient

            // Content
            $mail->isHTML(true); // Set email format to HTML
            $mail->Subject = 'Send Change Email';

            $mail->Body =
                "
           <p>" . 'hi ' .
                $data['firstname'] .
                ' ' .
                $data['lastname'] .
                ",</p>
           </br>
           <p>Your Password has been changed successfully.</p>
           <p> " . env('MAIL_FROM_NAME') . "</p>";

            $mail->send();
            return true;
        } catch (Exception $e) {
            //   dd($e);
            return false;
        }
    }

    public static function sendemailcustom($data)
    {
        $email_a = trim($data['email']);

        $mail = new PHPMailer(true);

        try {
            $mail->isSMTP(); // Send using SMTP
            $mail->Host = env('MAIL_HOST'); // Set the SMTP server to send through
            $mail->SMTPAuth = true; // Enable SMTP authentication
            $mail->Username = env('mail_username'); // SMTP username
            $mail->Password = env('MAIL_PASSWORD'); // SMTP password
            $mail->SMTPSecure = env('MAIL_ENCRYPTION'); // Enable TLS encryption; `PHPMailer::ENCRYPTION_SMTPS` also accepted
            $mail->Port = env('MAIL_PORT'); // TCP port to connect to

            $mail->SMTPOptions = [
                'ssl' => [
                    'verify_peer' => false,
                    'verify_peer_name' => false,
                    'allow_self_signed' => true,
                ],
            ];

            //Recipients
            $mail->setFrom(
                env('mail_username'),
                env('MAIL_FROM_NAME')
            );

            $mail->addAddress($email_a, $email_a);

            $mail->isHTML(true);
            $mail->Subject = $data['subject'];

            $mail->Body = $data['body'];

            $mail->send();
            return true;
        } catch (Exception $e) {
            //   dd($e);
            return false;
        }
    }

    public static function send_notification_FCM(
        $device_id,
        $data
    ) {
        // dd( $device_id);
        $make_data = [];

        $SERVER_API_KEY = env('SERVER_API_KEY');

        $linkRoute = '';
        $linkParam = '';
        switch ($data['type']) {
            case 1:
                $linkRoute = 'userTab';
                $linkParam = 'name';
                break;
            case 2:
                $linkRoute = 'bussinessInfo';
                $linkParam = 'businessDetails';
                break;
            case 3:
                $linkRoute = 'ChatScreen';
                $linkParam = 'name';
                break;
            default:
                $linkRoute = '';
                $linkParam = '';
                break;
        }

        $check_platform_ios = User::whereIn('device_id', $device_id)->where('platform', 'ios')->pluck('device_id');
        $check_platform_android = User::whereIn('device_id', $device_id)->where('platform', 'android')->pluck('device_id');

        $name = null;

        if ($data['notification_type'] == 'Chat') {
            $user_name = User::where('id', $data['receiver_id'])->first();
            $name = $user_name->firstname . ' ' . $user_name->lastname;
        }

        if (count($check_platform_ios) > 0) {
            $make_data = [
                'registration_ids' => $check_platform_ios,
                // 'contentAvailable' => true,
                'priority' => 'high',
                'data' => [
                    'body' => $data['message'],
                    'title' => $data['title'],
                    'type' => $data['notification_type'],
                    'user_id' => $data['user_id'],
                    'receiver_id' => $data['receiver_id'],
                    'entity_id' => $data['entity_id'],
                    // 'name' => $data['name'],
                    'message' => $data['message'],
                    'android_channel_id' => $data['notification_type'] == 'Chat' ? 'messages' : 'notification',
                    // 'link' =>
                    // 'pomillionapp://' .
                    //     $linkRoute .
                    //     '/' .
                    //     $id .
                    //     '?notification=true&&' .
                    //     $linkParam .
                    //     '=',
                ],
                "notification" => [
                    "body" => $data['message'],
                    "title" => $data['title'],
                ],
            ];

            // dd($make_data);
        }

        if (count($check_platform_android) > 0) {
            $make_data = [
                'registration_ids' => $check_platform_android,
                // 'contentAvailable' => true,
                'priority' => 'high',
                'data' => [
                    'body' => $data['message'],
                    'title' => $data['title'],
                    'type' => $data['notification_type'],
                    'user_id' => $data['user_id'],
                    'receiver_id' => $data['receiver_id'],
                    'entity_id' => $data['entity_id'],
                    // 'name' => $data['name'],
                    'message' => $data['message'],
                    'android_channel_id' => $data['notification_type'] == 'Chat' ? 'messages' : 'notification',
                    // 'link' =>
                    // 'pomillionapp://' .
                    //     $linkRoute .
                    //     '/' .
                    //     $id .
                    //     '?notification=true&&' .
                    //     $linkParam .
                    //     '=',
                ],
                // "notification" => [
                //     "body" => $message,
                //     "title" => $title,
                // ],
            ];
        }


        $dataString = json_encode($make_data);

        // dd( $dataString);

        $headers = [
            'Authorization: key=' . $SERVER_API_KEY,
            'Content-Type: application/json',
        ];

        $ch = curl_init();

        curl_setopt($ch, CURLOPT_URL, 'https://fcm.googleapis.com/fcm/send');
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $dataString);

        $response = curl_exec($ch);
        // dd($response);

        //curl_close($crl);
        //print_r($result_noti);die;
        return $response;
    }

    public static function saveSingleNotifications($data)
    {
        Log::info('Helper Data logged:', ['data' => $data]);
        $msgid = null;

        if ($data['device_id'] != null && $data['device_id'] != '') {

            // user notfication check preferences
            $user_id = [
                'user_id' => $data['receiver_id'],
                'parent_type' => $data['parent_type'],
            ];
            $user_notfication_pre = self::checkUserNotificationPreferences($user_id);

            $firebaseToken[] = $data['device_id'];

            if ($user_notfication_pre == false) {
                $returnVal = self::send_notification_FCM($firebaseToken, $data);
                try {
                    if (isset(json_decode($returnVal)->results[0]->message_id)) {
                        $msgid = json_decode($returnVal)->results[0]->message_id;
                    }
                } catch (Exception $e) {
                }
            }
        }

        Notification::create([
            'user_id' => $data['user_id'],
            'type' => $data['notification_type'],
            'title' => $data['title'],
            'message' => $data['message'],
            'message_id' => $msgid,
            'entity_id' => $data['entity_id'],
            'receiver_id' => $data['receiver_id'],
            'show_in_history' => $data['show_in_history'],
            'parent_type' => $data['parent_type'],
            'status' => 'active',
        ]);
    }

    public static function sendEmails($data)
    {
        
            $receiver = User::where('id', $data['receiver_id'])->first();

            $email = $receiver->email;

            $mail = new PHPMailer(true);

            try {
                $mail->isSMTP(); // Send using SMTP
                $mail->Host = env('MAIL_HOST'); // Set the SMTP server to send through
                $mail->SMTPAuth = true; // Enable SMTP authentication
                $mail->Username = env('mail_username'); // SMTP username
                $mail->Password = env('MAIL_PASSWORD'); // SMTP password
                $mail->SMTPSecure = env('MAIL_ENCRYPTION'); // Enable TLS encryption; `PHPMailer::ENCRYPTION_SMTPS` also accepted
                $mail->Port = env('MAIL_PORT'); // TCP port to connect to

                $mail->SMTPOptions = [
                    'ssl' => [
                        'verify_peer' => false,
                        'verify_peer_name' => false,
                        'allow_self_signed' => true,
                    ],
                ];

                //Recipients
                $mail->setFrom(
                    env('mail_username'),
                    env('MAIL_FROM_NAME')
                );

                $mail->addAddress($email, $email);

                $mail->isHTML(true);
                $mail->Subject = $data['title'];

                $mail->Body = $data['message'];

                $mail->send();
                return true;
            } catch (Exception $e) {
                //   dd($e);
                return false;
            }
       
    }

    // public static function send_notification_FCM_2(
    //     $notification_id,
    //     $title,
    //     $auth_id,
    //     $name,
    //     $message,
    //     $id,
    //     $notification_type,
    //     $type
    // ) {
    //     // $SERVER_API_KEY =
    //     //     'AAAAapOMCJw:APA91bECxJrlNOpDcKb9IkEC6sbY0j9pkSvOixXiE1x2loW4Ypb4j5AVBYSzVlVg9_D8273x_fFUV-gU7ysmvqO0C2r_wU_usC85gUeyem2SKWwjUuViiHvTkNQP2E7Gnx5seAP20Rix';

    //     $SERVER_API_KEY = env('SERVER_API_KEY');

    //     $linkRoute = '';
    //     $linkParam = '';
    //     switch ($type) {
    //         case 1:
    //             $linkRoute = 'userTab';
    //             $linkParam = 'name';
    //             break;
    //         case 2:
    //             $linkRoute = 'bussinessInfo';
    //             $linkParam = 'businessDetails';
    //             break;
    //         case 3:
    //             $linkRoute = 'ChatScreen';
    //             $linkParam = 'name';
    //             break;
    //         default:
    //             $linkRoute = '';
    //             $linkParam = '';
    //             break;
    //     }

    //     $data = [
    //         'registration_ids' => $notification_id,
    //         'contentAvailable' => true,
    //         'priority' => 'high',
    //         'data' => [
    //             'body' => $message,
    //             'title' => $title,
    //             'authid' => $auth_id,
    //             'name' => $name,
    //             'type' => $notification_type,
    //             'id' => $id,
    //             'message' => $message,
    //             'android_channel_id' => 'notification',
    //             'link' =>
    //             'pomillionapp://' .
    //                 $linkRoute .
    //                 '/' .
    //                 $id .
    //                 '?notification=true&&' .
    //                 $linkParam .
    //                 '=',
    //         ],
    //         "notification" => [
    //             "body" => $message,
    //             "title" => $title,
    //         ],
    //     ];
    //     $dataString = json_encode($data);

    //     $headers = [
    //         'Authorization: key=' . $SERVER_API_KEY,
    //         'Content-Type: application/json',
    //     ];

    //     $ch = curl_init();

    //     curl_setopt($ch, CURLOPT_URL, 'https://fcm.googleapis.com/fcm/send');
    //     curl_setopt($ch, CURLOPT_POST, true);
    //     curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    //     curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    //     curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    //     curl_setopt($ch, CURLOPT_POSTFIELDS, $dataString);

    //     $response = curl_exec($ch);

    //     //curl_close($crl);
    //     // print_r($response);die;
    //     return $response;
    // }

    // public static function saveBulkNotifications(
    //     $users,
    //     $notification_type,
    //     $title,
    //     $body,
    //     $data_id,
    //     $show_in_history,
    //     $notification_id,
    //     $type
    // ) {
    //     $msgid = null;

    //     if (count($notification_id) > 0) {
    //         $returnVal = self::send_notification_FCM(
    //             $notification_id,
    //             $title,
    //             $body,
    //             $data_id,
    //             $notification_type,
    //             $type
    //         );
    //         try {

    //             // dd($returnVal);
    //             // $msgid = $returnVal ? json_decode($returnVal)->results[0]->message_id : $msgid;
    //         } catch (Exception $e) {
    //         }
    //     }

    //     foreach ($users as $user) {
    //         $messageId_ = $msgid;
    //         if ($user->device_id == null || $user->device_id == '') {
    //             $messageId_ = null;
    //         }

    //         Notification::create([
    //             'user_id' => $user->id,
    //             'notification_type' => $notification_type,
    //             'title' => $title,
    //             'message' => $body,
    //             'message_id' => $user->device_id != null ? $user->device_id : $messageId_,
    //             'entity_id' => $data_id,
    //             'show_in_history' => $show_in_history,
    //             'status' => 'active',
    //         ]);
    //     }
    // }



    public static function profilePercentage($user_id)
    {
        $user = User::where('id', $user_id)->first();
        $user_images = ProfilePicture::where('user_id', $user_id)->get();

        // if (condition) {
        //     # code...
        // }

        // $input['firstname']  = $input['firstname'];
        // $input['lastname']  = $input['lastname'];
        // $input['name']  = $input['firstname'] . ' ' . $input['lastname'];
        // $input['username']  = $username;
        // $input['email'] = $email;
        // $input['password'] = bcrypt($input['password']);
        // $input['role_id']  = $input['role_id'];
        // $input['status']  = 'pending';
    }

    public static function dayViewFormula($posts)
    {
        $results = [];
        // $datas = [];

        foreach ($posts as $post) {
            $likes = PostImpression::where('post_id', $post->id)
                ->where('status', 'active')
                ->groupBy('post_id')
                ->selectRaw('post_id, count(*) as likes_count')
                ->pluck('likes_count', 'post_id')
                ->sum();

            $comments = PostComment::where('post_id', $post->id)
                ->where('status', 'active')
                ->groupBy('post_id')
                ->selectRaw('post_id, count(*) as comments_count')
                ->pluck('comments_count', 'post_id')
                ->sum();

            $shares = PostComment::where('post_id', $post->id)
                ->where('status', 'active')
                ->groupBy('post_id')
                ->selectRaw('post_id, count(*) as shares_count')
                ->pluck('shares_count', 'post_id')
                ->sum();

            $followers = Follower::where('to_user_id', $post->user_id)
                ->where('status', 'active')
                ->groupBy('to_user_id')
                ->selectRaw('to_user_id, count(*) as followers_count')
                ->pluck('followers_count', 'to_user_id')
                ->sum();

            // $datas[] = [
            //     'post_id' => $post->id,
            //     'post_user_id' => $post->user_id,
            //     'like_count' => $likes,
            //     'comment_count' => $comments,
            //     'share_count' => $shares,
            //     'follower_count' => $followers,
            // ];

            $follower = $followers == 0 ? 1 : $followers;

            // Calculate the formula
            $result = ($likes + 1.5 * $comments + 2 * $shares) / $follower;

            $results[] = [
                'result' => $result,
                'post_id' => $post->id,
            ];


            // Calculate the formula
            // $result = ($likes + 1.5 * $comments + 2 * $shares) / $followers;

            // $results[] = [
            //     'result' => $result,
            //     'post_id' => $post->id,
            // ];
        }
        // return $datas;

        usort($results, function ($a, $b) {
            return $a['result'] < $b['result'];
        });

        return $results;
    }

    public static function recommendedNetwork($users)
    {
        $results = [];
        // $datas = [];

        foreach ($users as $user) {
            $post = InitiativePost::where('user_id', $user->id)->where('status', 'active');
            $post_count = $post->count();
            $post_ids = $post->pluck('id');
            $user_ids = $post->pluck('user_id');

            $likes_count = PostImpression::whereIn('post_id', $post_ids)
                ->where('status', 'active')
                ->count();

            // $comments = PostComment::where('post_id', $post->id)
            //     ->where('status', 'active')
            //     ->groupBy('post_id')
            //     ->selectRaw('post_id, count(*) as comments_count')
            //     ->pluck('comments_count', 'post_id')
            //     ->sum();

            // $shares = PostComment::where('post_id', $post->id)
            //     ->where('status', 'active')
            //     ->groupBy('post_id')
            //     ->selectRaw('post_id, count(*) as shares_count')
            //     ->pluck('shares_count', 'post_id')
            //     ->sum();

            $followers_count = Follower::whereIn('to_user_id', $user_ids)
                ->where('status', 'active')
                ->count();

            // $total3 = [
            //     'post' => $post_count,
            //     'likes' => $likes,
            //     'followers' => $followers,
            // ];

            // dd($total3);

            // $datas[] = [
            //     'post_id' => $post->id,
            //     'post_user_id' => $post->user_id,
            //     'like_count' => $likes,
            //     'comment_count' => $comments,
            //     'share_count' => $shares,
            //     'follower_count' => $followers,
            // ];

            // $follower = $followers == 0 ? 1 : $followers;

            // // Calculate the formula
            // $result = ($likes + 1.5 * $comments + 2 * $shares) / $follower;
            $result = $likes_count + $post_count * 0.3 + $followers_count * 0.1;

            $results[] = [
                'result' => $result,
                'user_id' => $user->id,
            ];


            // Calculate the formula
            // $result = ($likes + 1.5 * $comments + 2 * $shares) / $followers;

            // $results[] = [
            //     'result' => $result,
            //     'post_id' => $post->id,
            // ];
        }
        // return $datas;

        usort($results, function ($a, $b) {
            return $a['result'] < $b['result'];
        });

        return $results;
    }

    public static function blockedUsers($data)
    {
        $block_entities = BlockEntity::where('user_id', Auth::id())->where('type', 'user')->where('status', 'block')->pluck('entity_id');

        return $block_entities;
    }

    public static function  MailchimpUserCreate($data)
    {

        $api_key = env('MAILCHIMP_APIKEY');
        $server = env('MAILCHIMP_SERVER_PREFIX');
        $list_id = env('MAILCHIMP_LIST_ID');

        $client = new ApiClient();
        $client->setConfig([
            'apiKey' => $api_key,
            'server' => $server,
        ]);

        $listId = $list_id; // Replace with your actual list ID

        $batchData = [
            "members" => [
                [
                    "email_address" => $data->email,
                    "status" => "subscribed",
                    "merge_fields" => [
                        "FNAME" => $data->first_name,
                        "LNAME" => $data->last_name,
                    ],
                ],
            ],
        ];

        $response = $client->lists->batchListMembers($listId, $batchData);
        return $response;
        // dd( response()->json($response));
    }


    public static function  MailchimpUserCreateByparams($email, $first_name, $last_name)
    {

        $api_key = env('MAILCHIMP_APIKEY');
        $server = env('MAILCHIMP_SERVER_PREFIX');
        $list_id = env('MAILCHIMP_LIST_ID');

        $client = new ApiClient();
        $client->setConfig([
            'apiKey' => $api_key,
            'server' => $server,
        ]);

        $listId = $list_id; // Replace with your actual list ID

        $batchData = [
            "members" => [
                [
                    "email_address" => $email,
                    "status" => "subscribed",
                    "merge_fields" => [
                        "FNAME" => $first_name,
                        "LNAME" => $last_name,
                    ],
                ],
            ],
        ];

        $response = $client->lists->batchListMembers($listId, $batchData);
        return $response;
        // dd( response()->json($response));
    }

    public static function FileUpload($filePath_, $file_)
    {        
        $filePath = 'customer/' . Auth::user()->customer_id . '/' . $filePath_;        
        $file = $file_;
        $type = 'public';

        $uploadedFilePath = Storage::disk('s3')->put($filePath, file_get_contents($file), $type);
        
        $fileUrl = Storage::disk('s3')->url($uploadedFilePath);
        return $filePath;
    }

    public static function FileExist($filePath_) {
        if (Storage::disk('s3')->exists($filePath_)) {
            return true;
        } else {
            return false;
        }
    }

    public static function FileUpload_WithoutAuth($filePath_, $file_, $customer_id)
    {        
        $filePath = 'customer/' . $customer_id . '/' . $filePath_;
        $file = $file_;
        $type = 'public';

        $uploadedFilePath = Storage::disk('s3')->put($filePath, $file, $type);
        
        $fileUrl = Storage::disk('s3')->url($uploadedFilePath);
        return $filePath;
    }

    public static function GetFiles()
    {                
        return env('AWS_URL') . '/customer/' . Auth::user()->customer_id . '/';        
    }

    public static function getFollowers($data)
    {
        $auth_id = Auth::id();
        $blocked_user_ids = Helper::blockedUsers(null);

        $followers = Follower::where('to_user_id', $auth_id)->whereNotIn('from_user_id', $blocked_user_ids)->where('status', 'active')->orderBy('created_at', 'desc');
        return $followers;
    }

    public static function getFollowings($data)
    {
        $auth_id = Auth::id();
        $blocked_user_ids = Helper::blockedUsers(null);

        $followings = Follower::where('from_user_id', $auth_id)->whereNotIn('to_user_id', $blocked_user_ids)->where('status', 'active')->orderBy('created_at', 'desc');
        return $followings;
    }

    public static function checkUserNotificationPreferences($data)
    {
        $type = $data['parent_type'];
        $data = UserNotificationPreference::where('user_id', $data['user_id'])->where('is_allow', 0);

        switch ($type) {
            case 'followers':
                $data = $data->where('notif_type', 'followers');
                break;

            case 'post':
                $data->where('notif_type', 'post');
                break;

            case 'post_action':
                $data->where('notif_type', 'post_action');
                break;

            case 'endorsement':
                $data->where('notif_type', 'endorsement');
                break;

            case 'message':
                $data->where('notif_type', 'message');
                break;

            case 'initiative_post':
                $data->where('notif_type', 'initiative_post');
                break;

            case 'create_post':
                $data->where('notif_type', 'create_post');
                break;

            default:
                # code...
                break;
        }

        $data = $data->exists();

        return $data;
    }   
}
