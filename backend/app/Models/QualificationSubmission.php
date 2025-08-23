<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class QualificationSubmission extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'qualification_id',
        'unit_id',
        'lo_id',
        'ac_id',
        // 'attachment',
        'iqa_outcome',
        'iqa_comment',
        'status',
        'created_by',
        'updated_by',
        'created_at',
        'updated_at',
        'deleted_at',
        'feedback',
        'comments',
        'assessor_id',
        'iqa_id',
    ];
}
