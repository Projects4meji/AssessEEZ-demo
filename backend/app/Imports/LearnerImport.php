<?php

namespace App\Imports;



namespace App\Imports;

use App\Http\Helpers\Helper;
use App\Models\ImportLog;
use App\Models\Qualification;
use App\Models\Role;
use App\Models\User;
use App\Models\UserQualification;
use Carbon\Carbon;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Validator;
use Maatwebsite\Excel\Concerns\ToModel;
use Maatwebsite\Excel\Concerns\WithBatchInserts;
use Maatwebsite\Excel\Concerns\WithChunkReading;
use Maatwebsite\Excel\Concerns\WithHeadingRow;

class LearnerImport implements ToModel, WithHeadingRow, WithChunkReading
{
    protected $errors = []; // To store validation errors
    protected $rowNumber = 2; // To keep track of the row number
    protected $fileName; // To store the file name
    public $errorFileName; // To store the error file name

    public function __construct($fileName)
    {
        $this->fileName = $fileName;
        $this->errorFileName = Helper::GetFiles() . 'import_errors/errors_' . time() . '.txt';

    }

    public function model(array $row)
    {
        // dd( $row['qualification']);
        $currentRow = $this->rowNumber++;

        // Define validation rules
        $rules = [
            // 'role'          => 'required|exists:roles,role_name',
            'surname'       => 'required',
            'email'         => 'required|email',
            'referenceno'   => 'nullable',
            'firstname'     => 'nullable',
            'midlename'     => 'nullable',
            'learnernumber' => 'nullable',
            'qualification' => 'required|exists:qualifications,sub_title',
            'assessor'      => 'required|exists:users,code',
            'iqa'           => 'required|exists:users,code',
            'dob'           => 'nullable|date',
            'batchno'       => 'nullable',
            'contact'       => 'nullable',
            'dor'           => 'nullable|date',
            'address'       => 'nullable',
        ];

        // Validate the row data
        $validator = Validator::make($row, $rules);

        if ($validator->fails()) {
            $errors = implode(', ', $validator->errors()->all());


            if (Storage::disk('s3')->exists($this->errorFileName)) {
                // Get the existing content
                $existingContent = Storage::disk('s3')->get($this->errorFileName);
                // Append the new content to the existing content
                $content = $existingContent . "Row {$currentRow}: {$errors}";
            } else {
                // If the file doesn't exist, just set the new content
                $content = "Row {$currentRow}: {$errors}";
            }

            // Storage::append($this->errorFileName, "Row {$currentRow}: {$errors}");
            Storage::disk('s3')->put($this->errorFileName, $content);


            // Log errors and continue processing

            ImportLog::create([
                'line_number' => $currentRow,
                'message'     => implode(', ', $validator->errors()->all()),
                'file_name'   => $this->fileName
            ]);
            return null;
        }


        $existingUser = User::where('email', $row['email'])->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))->pluck('id');

        if (count($existingUser) > 0) {
            $existingQualifications = UserQualification::whereIn('user_id', $existingUser)
                ->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
                ->pluck('qualification_id')
                ->toArray();

            $newQualification = Qualification::where('sub_title', $row['qualification'])
            ->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
            ->pluck('id')->first();

            if (in_array($newQualification, $existingQualifications)) {
                $error = 'You are already registered with this email and qualifications: ' . $row['email'];
                
                //Storage::append($this->errorFileName, "Row {$currentRow}: {$error}");
                if (Storage::disk('s3')->exists($this->errorFileName)) {
                    // Get the existing content
                    $existingContent = Storage::disk('s3')->get($this->errorFileName);
                    // Append the new content to the existing content
                    $content = $existingContent . "Row {$currentRow}: {$error}";
                } else {
                    // If the file doesn't exist, just set the new content
                    $content = "Row {$currentRow}: {$error}";
                }
    
                // Storage::append($this->errorFileName, "Row {$currentRow}: {$errors}");
                Storage::disk('s3')->put($this->errorFileName, $content);



                ImportLog::create([
                    'line_number' => $currentRow,
                    'message'     => $error,
                    'file_name'   => $this->fileName
                ]);
                return null;
            }
        }

        // Check if email already exists
        // if (User::where('email', $row['email'])->exists()) {
        //     $error = 'User with this email already exists: ' . $row['email'];
        //     Storage::append($this->errorFileName, "Row {$currentRow}: {$error}");
        //     ImportLog::create([
        //         'line_number' => $currentRow,
        //         'message'     => 'User with this email already exists: ' . $row['email'],
        //         'file_name'   => $this->fileName
        //     ]);
        //     return null;
        // }

        $qualification = null;
        $assessor = null;
        $iqa = null;

        if ($row['qualification']) {
            $qualification = Qualification::where('sub_title', $row['qualification'])
            ->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
            ->first();
        }

        $existing_user = User::where('email', $row['email'])
        ->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
        ->first();

        if ($existing_user == null) {
            $password = str()->random(8);
            $user = User::create([
                'role_id'              => 3,
                'email'                => $row['email'],
                'password'             => Hash::make($password),
                'customer_id' => Auth::user()->customer_id,
                'created_by' => Auth::id(),
                'updated_by' => Auth::id()
            ]);           

                $InstituteDetail = User::where('id', Helper::getCompanyAdminId(Auth::id()))->first();                

                    $InstituteName = null;
                    if ($InstituteDetail->first_name != null) {
                        $InstituteName .= $InstituteDetail->first_name;
                    }
            
                    if ($InstituteDetail->middle_name != null) {
                        $InstituteName .= ($InstituteName != null ? ' ' : '') . $InstituteDetail->middle_name;
                    }
            
                    if ($InstituteDetail->sur_name != null) {
                        $InstituteName .= ($InstituteName != null ? ' ' : '') . $InstituteDetail->sur_name;
                    }                    

                $credentials = [
                    'email' => $row['email'],
                    'password' => $password,
                    'role' => 3,
                    'institute' => $qualification->sub_title,
                ];
                
                Helper::createUserCredentials($credentials);
            

        } else {
            $user = $existing_user;
        }

        // User Qualification

        if ($user) {
            UserQualification::create([
                'user_id'              => $user->id,
                'ref_number'           => $row['referenceno'],
                'first_name'           => $row['firstname'],
                'midle_name'          => $row['midlename'],
                'sur_name'             => $row['surname'],
                'learner_number'       => $row['learnernumber'],
                'qualification_id'     => $qualification->id,
                'date_of_registration' => isset($row['dor']) ? Carbon::parse($row['dor'])->format('Y-m-d') : null,
                'cohort_batch_no'      => $row['batchno'],
                'contact'              => $row['contact'],
                'date_of_birth'        => isset($row['dob']) ? Carbon::parse($row['dob'])->format('Y-m-d') : null,
                'address'              => $row['address'],
                'created_by' => Auth::id(),
                'updated_by' => Auth::id()
            ]);
        }

        // Insert assessor data into user_assessors table
        if ($row['assessor']) {

            $assessor_code =  str_pad($row['assessor'], 5, '0', STR_PAD_LEFT);

            $assessor = User::where('code', $assessor_code)
            ->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
            ->first();
            if ($assessor) {
                DB::table('user_assessors')->insert([
                    'user_id' => $user->id,
                    'assessor_id' => $assessor->id,
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id()
                ]);
            }
        }

        // Insert IQA data into user_iqas table
        if ($row['iqa']) {

            $iqa_code =  str_pad($row['iqa'], 5, '0', STR_PAD_LEFT);

            $iqa = User::where('code', $iqa_code)
            ->whereIn('created_by', Helper::getAdmin_ids(Auth::id()))
            ->first();
            if ($iqa) {
                DB::table('user_iqas')->insert([
                    'user_id' => $user->id,
                    'iqa_id' => $iqa->id,
                    'created_by' => Auth::id(),
                    'updated_by' => Auth::id()
                ]);
            }
        }

        return $user;
    }

    public function chunkSize(): int
    {
        return 1000; // Adjust this based on your needs
    }
}
