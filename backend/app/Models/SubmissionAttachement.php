<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
// use Illuminate\Database\Eloquent\SoftDeletes;

class SubmissionAttachement extends Model
{
    use HasFactory;

    protected $fillable = [
        'id',
        'qualification_id',
        'submission_id',
        'attachement',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at',
    ];
}
