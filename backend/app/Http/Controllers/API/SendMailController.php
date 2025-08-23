<?php

namespace App\Http\Controllers\API;


use App\Http\Controllers\Controller;
use App\Http\Helpers\Helper;
use App\Http\Resources\AssessorDocumenResource;
use App\Http\Resources\AssessorResource;
use App\Http\Resources\CommunicationResource;
use App\Http\Resources\CustomerResource;
use App\Http\Resources\RoleResource;
use App\Http\Resources\UserLoginResource;
use App\Http\Resources\UserNameResource;
use App\Http\Resources\UserResource;
use App\Imports\LearnerImport;
use App\Imports\UsersImport;
use App\Mail\BulkEditUserMail;
use App\Models\AssessorDocument;
use App\Models\Communication;
use App\Models\Customer;
use App\Models\Order;
use App\Models\Otp;
use App\Models\Product;
use App\Models\Qualification;
use App\Models\QualificationAc;
use App\Models\QualificationDocument;
use App\Models\QualificationSubmission;
use App\Models\RequestPayment;
use App\Models\Role;
use App\Models\SubmissionAttachement;
use App\Models\Type;
use App\Models\UpdateUserDetailLog;
use App\Models\User;
use App\Models\UserAssessor;
use App\Models\UserIqa;
use App\Models\UserLearner;
use App\Models\UserQualification;
use App\Models\UserReference;
use App\Models\UserRole;
use Carbon\Carbon;
use Exception;
use GuzzleHttp\Client;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\URL;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Maatwebsite\Excel\Facades\Excel;

class SendMailController extends Controller
{
    public function sendCredentials(Request $request)
    {
        $email = $request->input('email');

        // Validate the email (optional but recommended)
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            return response()->json(['error' => 'Invalid email address'], 400);
        }

        // Example data for demonstration purposes
        $data = [
            'email' => $email,
            'password' => 'password123', // Replace with actual password generation
            'role' => 3, // Replace with actual role ID
            'institute' => 'Example Institute', // Replace with actual institute name
            'qualification' => 'Example Qualification', // Replace with actual qualification
        ];

        // Call the Helper function
        Helper::createUserCredentials($data);

        return response()->json(['message' => 'Credentials sent successfully'], 200);
    }
}
